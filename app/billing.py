"""Plans, monthly usage limits, Stripe subscriptions per organisation, leads and funnel events.

Billing is OFF unless CFA_BILLING=on, so self-hosted and development installs stay unlimited.
Every organisation has its own row in `org_billing` (plan, status, Stripe customer and
subscription, period end, grace period) and its own counters in `org_usage`.

Stripe has not been run against the live service from this repository: use test mode and
`stripe listen` first (docs/BILLING.md describes the exact walkthrough).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()
STRIPE_TRANSPORT: httpx.AsyncBaseTransport | None = None
BIG = 1_000_000

# Launch prices and limits are hypotheses to test with real customers, not facts.
PLANS: dict[str, dict[str, Any]] = {
    "free": {"name": "Free", "price_eur": 0, "tagline": "Try it with your own notes",
             "limits": {"agents": 4, "messages": 50, "calls": 3, "research": 3, "uploads": 5,
                        "mcp_servers": 0, "seats": 3, "api_calls": 2_000, "audit_days": 7, "storage_mb": 25}},
    "starter": {"name": "Starter", "price_eur": 29, "tagline": "For one person running real work",
                "limits": {"agents": 10, "messages": 1_000, "calls": 30, "research": 30, "uploads": 50,
                           "mcp_servers": 1, "seats": 10, "api_calls": 20_000, "audit_days": 30, "storage_mb": 250}},
    "professional": {"name": "Professional", "price_eur": 99, "tagline": "Team governance with live tools",
                     "limits": {"agents": 25, "messages": 5_000, "calls": 150, "research": 150, "uploads": 300,
                                "mcp_servers": 5, "seats": 25, "api_calls": 100_000, "audit_days": 90, "storage_mb": 1_000}},
    "enterprise": {"name": "Enterprise", "price_eur": None, "tagline": "Custom limits, invoiced",
                   "limits": {"agents": 100, "messages": 25_000, "calls": 1_000, "research": 1_000, "uploads": 2_000,
                              "mcp_servers": 25, "seats": 200, "api_calls": 500_000, "audit_days": 365, "storage_mb": 10_000}},
}
# Plans that existed before the rename. Read-only compatibility for rows already in the database.
ALIASES = {"pro": "professional", "team": "professional", "pilot": "enterprise", "business": "professional"}

LABEL = {"agents": "agents", "messages": "agent messages", "calls": "council calls", "research": "deep research runs",
         "uploads": "file uploads", "mcp_servers": "live MCP servers", "seats": "team members", "api_calls": "API calls",
         "storage_mb": "stored knowledge"}
MONTHLY = ("messages", "calls", "research", "uploads", "api_calls")
STRIPE_PLANS = ("starter", "professional", "enterprise")


def enabled() -> bool:
    return os.getenv("CFA_BILLING") == "on"


def canonical(plan: str | None) -> str:
    p = (plan or "").strip().lower()
    p = ALIASES.get(p, p)
    return p if p in PLANS else "free"


def limits_for(plan: str) -> dict[str, int]:
    return PLANS[canonical(plan)]["limits"]


CORE_AGENTS = ("strategist", "skeptic", "builder", "chair")


def agent_count(con) -> int:
    """Agents you created or imported. The four built-in council agents are free on every plan."""
    return con.execute("SELECT COUNT(*) FROM bots WHERE id NOT IN (?,?,?,?) AND org_id=?",
                       (*CORE_AGENTS, pf.org())).fetchone()[0]


def storage_bytes(con) -> int:
    """Stored knowledge of the current organisation: note bodies plus research reports."""
    org = pf.org()
    note = con.execute("SELECT COALESCE(SUM(LENGTH(body)),0) FROM notes WHERE org_id=?", (org,)).fetchone()[0]
    research = con.execute("SELECT COALESCE(SUM(LENGTH(report)),0) FROM research WHERE org_id=?", (org,)).fetchone()[0]
    return int(note) + int(research)


def storage_mb(con) -> float:
    return round(storage_bytes(con) / 1_048_576, 2)


def check_storage(con, adding_bytes: int) -> None:
    """Refuse an upload that would push the organisation over its plan storage."""
    if not enabled():
        return
    plan = current_plan(con)
    limit_mb = PLANS[plan]["limits"].get("storage_mb")
    if not limit_mb:
        return
    used = storage_bytes(con)
    if used + adding_bytes > limit_mb * 1_048_576:
        raise _deny("storage_mb", plan, limit_mb, round(used / 1_048_576, 2))


def member_count(con) -> int:
    return con.execute("SELECT COUNT(*) FROM users WHERE org_id=? AND status='active'", (pf.org(),)).fetchone()[0]


def member_count_org(org_id: str) -> int:
    """Seat count of a specific organisation (invitations run before the session is switched)."""
    with pf.db() as con:
        return con.execute("SELECT COUNT(*) FROM users WHERE org_id=? AND status='active'", (org_id,)).fetchone()[0]


def _columns(con) -> None:
    """org_billing gained grace/cancel columns after the first multi-tenant release."""
    have = {r[1] for r in con.execute("PRAGMA table_info(org_billing)")}
    for col, ddl in (("grace_until", "TEXT"), ("cancel_at_period_end", "INTEGER DEFAULT 0"),
                     ("currency", "TEXT DEFAULT 'EUR'"), ("last_invoice_status", "TEXT")):
        if col not in have:
            con.execute(f"ALTER TABLE org_billing ADD COLUMN {col} {ddl}")


def _billing_row(con, org_id: str):
    """The organisation's billing row; legacy deployments fall back to the pre-tenancy row."""
    _columns(con)
    r = con.execute("SELECT * FROM org_billing WHERE org_id=?", (org_id,)).fetchone()
    if r is None and org_id == pf.DEFAULT_ORG:
        r = con.execute("SELECT * FROM billing WHERE id=1").fetchone()
    return r


def _grace_days() -> int:
    try:
        return max(0, int(os.getenv("CFA_GRACE_DAYS", "3")))
    except ValueError:
        return 3


def current_plan(con) -> str:
    """The effective plan of the current organisation, including the past-due grace period."""
    r = _billing_row(con, pf.org())
    if r:
        plan = canonical(r["plan"])
        status = r["status"]
        if status in ("active", "trialing"):
            return plan
        if status == "past_due":
            grace = r["grace_until"] if "grace_until" in r.keys() else None
            return plan if (grace and grace > pf._m().now()) else "free"
        if status in ("canceled", "unpaid", "incomplete_expired"):
            return "free"
    forced = os.getenv("CFA_PLAN")
    return canonical(forced) if forced else "free"


def _used(con, period: str, metric: str) -> int:
    row = con.execute("SELECT n FROM org_usage WHERE org_id=? AND period=? AND metric=?",
                      (pf.org(), period, metric)).fetchone()
    return row["n"] if row else 0


def _deny(metric: str, plan: str, limit: int, used: int) -> HTTPException:
    return HTTPException(402, {"code": "limit_reached", "metric": metric, "label": LABEL[metric], "limit": limit,
                               "used": used, "plan": plan,
                               "message": f"You reached the {PLANS[plan]['name']} plan limit for {LABEL[metric]} ({limit}). Upgrade to continue."})


def use(metric: str, amount: int = 1) -> None:
    """Count one unit of a monthly metric; raises 402 when the plan limit is reached."""
    if not enabled():
        return
    period = pf._m().now()[:7]
    with pf.db() as con:
        _columns(con)
        plan = current_plan(con)
        limit = PLANS[plan]["limits"].get(metric)
        if limit is None:
            return
        used = _used(con, period, metric)
        if used + amount > limit:
            raise _deny(metric, plan, limit, used)
        con.execute("INSERT INTO org_usage (org_id, period, metric, n) VALUES (?,?,?,?) "
                    "ON CONFLICT(org_id, period, metric) DO UPDATE SET n = n + ?",
                    (pf.org(), period, metric, amount, amount))


def check_count(metric: str, current: int, adding: int = 1) -> None:
    """Seat/agent limits: compare the current number of objects against the plan."""
    if not enabled():
        return
    with pf.db() as con:
        plan = current_plan(con)
    limit = PLANS[plan]["limits"].get(metric)
    if limit is not None and current + adding > limit:
        raise _deny(metric, plan, limit, current)


def meter_api_call(path: str) -> None:
    """Count one API call for the organisation. Called by the HTTP middleware.

    Read-only endpoints that the UI polls are still counted: the plan metric is about load,
    and hiding polls would make the number a lie.
    """
    if not enabled() or not path.startswith("/api/"):
        return
    if path.startswith(("/api/health", "/api/auth/", "/api/public", "/api/billing")):
        return
    use("api_calls")


@router.get("/api/public")
def public_info() -> dict[str, Any]:
    """What the public pages (/welcome, /trust) may show: prices, contacts and the version. No workspace data."""
    return {"version": pf.VERSION, "contact": os.getenv("CFA_CONTACT_URL", ""),
            "security_contact": os.getenv("CFA_SECURITY_CONTACT", ""),
            "plans": [{"id": k, "name": v["name"], "price_eur": v["price_eur"], "tagline": v["tagline"],
                       "limits": v["limits"]} for k, v in PLANS.items()]}


@router.get("/api/billing")
def billing() -> dict[str, Any]:
    period = pf._m().now()[:7]
    with pf.db() as con:
        _columns(con)
        plan = current_plan(con)
        row = _billing_row(con, pf.org())
        usage = {r["metric"]: r["n"] for r in con.execute(
            "SELECT metric,n FROM org_usage WHERE org_id=? AND period=?", (pf.org(), period))}
        usage["agents"] = agent_count(con)
        usage["seats"] = member_count(con)
        usage["mcp_servers"] = con.execute("SELECT COUNT(*) FROM mcp_servers WHERE org_id=?", (pf.org(),)).fetchone()[0]
    keys = ("customer_id", "subscription_id", "period_end", "grace_until", "cancel_at_period_end", "status", "last_invoice_status")
    rowd = {k: row[k] for k in keys if row and k in row.keys()} if row else {}
    stripe_ready = bool(os.getenv("STRIPE_SECRET_KEY") and any(os.getenv(f"STRIPE_PRICE_{p.upper()}") for p in STRIPE_PLANS))
    return {"enabled": enabled(), "plan": plan, "plan_name": PLANS[plan]["name"],
            "plan_locked": bool(os.getenv("CFA_PLAN")), "status": rowd.get("status") or "active",
            "period_end": rowd.get("period_end"), "grace_until": rowd.get("grace_until"),
            "cancel_at_period_end": bool(rowd.get("cancel_at_period_end") or 0),
            "last_invoice_status": rowd.get("last_invoice_status"),
            "limits": PLANS[plan]["limits"], "usage": {k: usage.get(k, 0) for k in LABEL}, "labels": LABEL,
            "plans": [{"id": k, "name": v["name"], "price_eur": v["price_eur"], "tagline": v["tagline"],
                       "limits": v["limits"]} for k, v in PLANS.items()],
            "checkout": stripe_ready, "portal": bool(rowd.get("customer_id") and os.getenv("STRIPE_SECRET_KEY")),
            "contact": os.getenv("CFA_CONTACT_URL", "")}


@router.get("/api/org/revenue")
def revenue(request: Request) -> dict[str, Any]:
    """Revenue view of the caller's organisation: plan price, seats, MRR/ARR and subscription state.

    The numbers are derived from the plan and the billing row; they are not an accounting ledger.
    """
    pf.need_admin(request)
    with pf.db() as con:
        _columns(con)
        plan = current_plan(con)
        row = _billing_row(con, pf.org())
        seats = member_count(con)
        org = con.execute("SELECT created_at FROM orgs WHERE id=?", (pf.org(),)).fetchone()
    price = PLANS[plan]["price_eur"] or 0
    status = (row["status"] if row else "active") or "active"
    invoice_status = (row["last_invoice_status"] if row and "last_invoice_status" in row.keys() else None)
    return {"org": pf.org(), "plan": plan, "plan_name": PLANS[plan]["name"], "currency": "EUR",
            "price_eur": PLANS[plan]["price_eur"], "seats": seats, "mrr_eur": price * 1 if status in ("active", "trialing") else 0,
            "arr_eur": (price * 12) if status in ("active", "trialing") else 0,
            "status": status, "last_invoice_status": invoice_status,
            "period_end": row["period_end"] if row else None, "grace_until": row["grace_until"] if row else None,
            "customer_since": org["created_at"] if org else None,
            "note": "Derived from the plan price and subscription status; invoices stay in Stripe."}


@router.get("/api/admin/revenue")
def revenue_all(request: Request) -> dict[str, Any]:
    """Operator view: MRR/ARR across all organisations. Super admin only."""
    principal = pf._principal(request)
    from app import auth
    if auth.rank(principal.get("role")) < auth.rank("super_admin"):
        raise HTTPException(403, "super admin required")
    with pf.db() as con:
        _columns(con)
        rows = con.execute("SELECT o.id, o.name, o.created_at, b.plan, b.status FROM orgs o "
                           "LEFT JOIN org_billing b ON b.org_id = o.id").fetchall()
    orgs, mrr = [], 0.0
    for r in rows:
        plan = canonical(r["plan"] or "free")
        status = r["status"] or "active"
        price = PLANS[plan]["price_eur"] or 0
        amount = price if status in ("active", "trialing") else 0
        mrr += amount
        orgs.append({"id": r["id"], "name": r["name"], "plan": plan, "status": status,
                     "mrr_eur": amount, "since": r["created_at"]})
    return {"organisations": len(orgs), "mrr_eur": round(mrr, 2), "arr_eur": round(mrr * 12, 2), "rows": orgs}


# ---------- Stripe ----------
async def _stripe(path: str, data: dict[str, str] | None = None, method: str = "POST") -> dict[str, Any]:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise HTTPException(503, "Stripe is not configured on this deployment")
    try:
        async with httpx.AsyncClient(transport=STRIPE_TRANSPORT, timeout=20, base_url="https://api.stripe.com") as c:
            r = await c.request(method, path, data=data, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        raise HTTPException(502, "Stripe could not be reached")
    if r.status_code >= 400:
        raise HTTPException(502, "Stripe rejected the request")
    return r.json()


def _base(request: Request) -> str:
    return (os.getenv("APP_URL") or str(request.base_url)).rstrip("/")


def _iso(ts: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(ts), timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


class CheckoutIn(BaseModel):
    plan: str = Field(pattern="^(starter|professional|enterprise|pro|team|pilot)$")


@router.post("/api/billing/checkout")
async def checkout(item: CheckoutIn, request: Request) -> dict[str, str]:
    p = pf.need_admin(request)
    plan = canonical(item.plan)
    if plan not in STRIPE_PLANS:
        raise HTTPException(422, "this plan is not sold through Stripe; use the pilot process")
    price = os.getenv(f"STRIPE_PRICE_{plan.upper()}")
    if not price:
        raise HTTPException(503, "this plan has no Stripe price configured")
    base, oid = _base(request), pf.org()
    with pf.db() as con:
        row = _billing_row(con, oid)
    data = {"mode": "subscription", "line_items[0][price]": price, "line_items[0][quantity]": "1",
            "success_url": base + "/?billing=success", "cancel_url": base + "/?billing=cancel",
            "client_reference_id": oid, "metadata[plan]": plan, "metadata[org_id]": oid,
            "subscription_data[metadata][plan]": plan, "subscription_data[metadata][org_id]": oid,
            "allow_promotion_codes": "true"}
    if row and row["customer_id"]:
        data["customer"] = row["customer_id"]
    url = (await _stripe("/v1/checkout/sessions", data)).get("url", "")
    if not url.startswith("https://checkout.stripe.com/"):
        raise HTTPException(502, "unexpected checkout address")
    pf._m().append_audit("billing.checkout_started", p["name"], {"plan": plan})
    return {"url": url}


@router.post("/api/billing/portal")
async def portal(request: Request) -> dict[str, str]:
    pf.need_admin(request)
    with pf.db() as con:
        row = _billing_row(con, pf.org())
    if not row or not row["customer_id"]:
        raise HTTPException(409, "there is no paid subscription yet")
    url = (await _stripe("/v1/billing_portal/sessions", {"customer": row["customer_id"], "return_url": _base(request)})).get("url", "")
    if not url.startswith("https://billing.stripe.com/"):
        raise HTTPException(502, "unexpected portal address")
    return {"url": url}


@router.get("/api/billing/invoices")
async def invoices(request: Request) -> dict[str, Any]:
    """The organisation's invoices, straight from Stripe. Nothing is cached or invented."""
    pf.need_admin(request)
    with pf.db() as con:
        row = _billing_row(con, pf.org())
    if not row or not row["customer_id"]:
        return {"invoices": [], "note": "No Stripe customer for this organisation yet."}
    data = await _stripe(f"/v1/invoices?customer={row['customer_id']}&limit=12", None, "GET")
    out = [{"id": i.get("id"), "number": i.get("number"), "status": i.get("status"),
            "amount_due": i.get("amount_due"), "amount_paid": i.get("amount_paid"),
            "currency": i.get("currency"), "created": _iso(i.get("created")),
            "period_end": _iso(i.get("period_end")), "hosted_invoice_url": i.get("hosted_invoice_url"),
            "invoice_pdf": i.get("invoice_pdf")} for i in (data.get("data") or [])]
    return {"invoices": out, "customer": row["customer_id"]}


class CancelIn(BaseModel):
    at_period_end: bool = True


@router.post("/api/billing/cancel")
async def cancel(item: CancelIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    with pf.db() as con:
        row = _billing_row(con, pf.org())
    if not row or not row["subscription_id"]:
        raise HTTPException(409, "there is no subscription to cancel")
    await _stripe(f"/v1/subscriptions/{row['subscription_id']}",
                  {"cancel_at_period_end": "true" if item.at_period_end else "false"})
    with pf.db() as con:
        _set_billing(con, pf.org(), cancel_at_period_end=1 if item.at_period_end else 0)
    pf._m().append_audit("billing.cancel_requested", p["name"], {"at_period_end": item.at_period_end})
    return {"ok": True, "cancel_at_period_end": item.at_period_end}


@router.post("/api/billing/resume")
async def resume(request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    with pf.db() as con:
        row = _billing_row(con, pf.org())
    if not row or not row["subscription_id"]:
        raise HTTPException(409, "there is no subscription to resume")
    await _stripe(f"/v1/subscriptions/{row['subscription_id']}", {"cancel_at_period_end": "false"})
    with pf.db() as con:
        _set_billing(con, pf.org(), cancel_at_period_end=0)
    pf._m().append_audit("billing.cancel_reverted", p["name"], {})
    return {"ok": True, "cancel_at_period_end": False}


def verify_stripe(payload: bytes, header: str, secret: str, tolerance: int = 300, now: float | None = None) -> bool:
    try:
        parts = dict(x.split("=", 1) for x in header.split(",") if "=" in x)
        t = int(parts["t"])
    except (KeyError, ValueError):
        return False
    sigs = [x.split("=", 1)[1] for x in header.split(",") if x.startswith("v1=")]
    if abs((now if now is not None else time.time()) - t) > tolerance:
        return False
    good = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(good, s) for s in sigs)


def _price_to_plan(price_id: str | None) -> str | None:
    for plan in STRIPE_PLANS:
        if price_id and price_id == os.getenv(f"STRIPE_PRICE_{plan.upper()}"):
            return plan
    return None


def _set_billing(con, org_id: str, **kw: Any) -> None:
    _columns(con)
    con.execute("INSERT OR IGNORE INTO org_billing (org_id,plan,status,updated_at) VALUES (?,'free','active',?)",
                (org_id, pf._m().now()))
    for k, v in kw.items():
        con.execute(f"UPDATE org_billing SET {k}=?, updated_at=? WHERE org_id=?", (v, pf._m().now(), org_id))


def _event_org(con, kind: str, obj: dict[str, Any]) -> str:
    """The organisation a Stripe event belongs to: checkout reference, metadata, then known billing rows."""
    meta = obj.get("metadata") or {}
    oid = obj.get("client_reference_id") or meta.get("org_id") or meta.get("org")
    if oid and oid != "workspace":  # pre-multi-tenancy checkouts used the literal "workspace"
        return str(oid)
    if kind.startswith("customer.subscription.") and obj.get("id"):
        r = con.execute("SELECT org_id FROM org_billing WHERE subscription_id=? LIMIT 1", (obj["id"],)).fetchone()
        if r:
            return r["org_id"]
    if obj.get("subscription"):
        r = con.execute("SELECT org_id FROM org_billing WHERE subscription_id=? LIMIT 1", (obj["subscription"],)).fetchone()
        if r:
            return r["org_id"]
    if obj.get("customer"):
        r = con.execute("SELECT org_id FROM org_billing WHERE customer_id=? LIMIT 1", (obj["customer"],)).fetchone()
        if r:
            return r["org_id"]
    return pf.DEFAULT_ORG  # events from before multi-tenancy belong to the legacy workspace


@router.post("/api/billing/webhook")
async def webhook(request: Request) -> dict[str, bool]:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(503, "webhook secret is not configured")
    payload = await request.body()
    if not verify_stripe(payload, request.headers.get("stripe-signature", ""), secret):
        raise HTTPException(400, "invalid signature")
    ev = json.loads(payload)
    obj = (ev.get("data") or {}).get("object") or {}
    with pf.db() as con:
        if con.execute("SELECT 1 FROM stripe_events WHERE id=?", (ev.get("id"),)).fetchone():
            return {"received": True}
        con.execute("INSERT INTO stripe_events VALUES (?,?)", (ev.get("id"), pf._m().now()))
        kind, changed = ev.get("type", ""), None
        oid = _event_org(con, kind, obj)
        if kind == "checkout.session.completed" and obj.get("mode") == "subscription":
            plan = canonical((obj.get("metadata") or {}).get("plan"))
            if plan in STRIPE_PLANS or plan == "free":
                _set_billing(con, oid, plan=plan, status="active", customer_id=obj.get("customer"),
                             subscription_id=obj.get("subscription"), grace_until=None)
                changed = plan
        elif kind in ("customer.subscription.created", "customer.subscription.updated"):
            price = (((obj.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get("id")
            plan = _price_to_plan(price) or canonical((obj.get("metadata") or {}).get("plan"))
            status = obj.get("status", "active")
            _set_billing(con, oid, plan=plan, status=status, customer_id=obj.get("customer"),
                         subscription_id=obj.get("id"), period_end=_iso(obj.get("current_period_end")),
                         cancel_at_period_end=1 if obj.get("cancel_at_period_end") else 0,
                         grace_until=None if status in ("active", "trialing") else None)
            changed = plan
        elif kind == "customer.subscription.deleted":
            _set_billing(con, oid, plan="free", status="canceled", subscription_id=None,
                         period_end=_iso(obj.get("ended_at")), cancel_at_period_end=0)
            changed = "free"
        elif kind in ("invoice.payment_failed", "invoice.payment_action_required"):
            grace = (datetime.now(timezone.utc) + timedelta(days=_grace_days())).isoformat()
            _set_billing(con, oid, status="past_due", grace_until=grace, last_invoice_status="failed")
            changed = "past_due"
        elif kind == "invoice.paid":
            _set_billing(con, oid, status="active", grace_until=None, last_invoice_status="paid",
                         period_end=_iso((((obj.get("lines") or {}).get("data") or [{}])[0].get("period") or {}).get("end")))
            changed = "active"
        elif kind == "invoice.payment_succeeded":
            _set_billing(con, oid, last_invoice_status="paid", grace_until=None)
            changed = "paid"
        elif kind == "customer.subscription.trial_will_end":
            _set_billing(con, oid, status="trialing")
            changed = "trialing"
    if changed:
        pf._m().append_audit("billing.plan_changed", "stripe", {"event": ev.get("type"), "to": changed, "org_id": oid})
    return {"received": True}


# ---------- leads and funnel ----------
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,200}\.[A-Za-z]{2,}$")
EVENTS = ("welcome_view", "cta_pilot", "cta_demo", "cta_pricing", "trust_view", "upgrade_click", "preset_applied", "signup_started")


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=254)
    company: str = Field(default="", max_length=120)
    message: str = Field(default="", max_length=1000)
    source: str = Field(default="welcome", max_length=40)
    website: str = Field(default="", max_length=200)  # honeypot: real visitors leave it empty


@router.post("/api/leads", status_code=201)
async def lead(item: LeadIn) -> dict[str, bool]:
    if item.website:
        return {"ok": True}  # silently drop bots
    if not EMAIL.match(item.email):
        raise HTTPException(422, "please enter a valid email address")
    with pf.db() as con:
        con.execute("INSERT INTO leads (id,created_at,name,email,company,message,source,org_id) VALUES (?,?,?,?,?,?,?,?)",
                    (uuid4().hex[:10], pf._m().now(), item.name.strip(), item.email.strip().lower(),
                     item.company.strip(), item.message.strip(), item.source, pf.org()))
    hook = os.getenv("CFA_LEADS_WEBHOOK", "")
    if hook.startswith("https://"):
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                await c.post(hook, json={"text": f"New Shewiun lead: {item.name} <{item.email}> {item.company}"})
        except httpx.HTTPError:
            pass  # the lead is stored either way
    return {"ok": True}


@router.get("/api/leads")
def leads(request: Request) -> list[dict[str, Any]]:
    pf.need_admin(request)
    with pf.db() as con:
        return [dict(r) for r in con.execute("SELECT id,created_at,name,email,company,message,source FROM leads WHERE org_id=? "
                                             "ORDER BY created_at DESC LIMIT 200", (pf.org(),))]


class EventIn(BaseModel):
    name: str = Field(max_length=30)


@router.post("/api/events", status_code=201)
def event(item: EventIn) -> dict[str, bool]:
    if item.name not in EVENTS:
        raise HTTPException(422, "unknown event")
    day = pf._m().now()[:10]
    with pf.db() as con:
        con.execute("INSERT INTO org_events (org_id,day,name,n) VALUES (?,?,?,1) ON CONFLICT(org_id, day, name) DO UPDATE SET n = n + 1",
                    (pf.org(), day, item.name))
    return {"ok": True}


@router.get("/api/events/summary")
def events_summary(request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    with pf.db() as con:
        rows = con.execute("SELECT name, SUM(n) AS n FROM org_events WHERE org_id=? AND day >= date('now','-30 day') GROUP BY name",
                           (pf.org(),)).fetchall()
        leads_n = con.execute("SELECT COUNT(*) FROM leads WHERE org_id=?", (pf.org(),)).fetchone()[0]
    return {"last_30_days": {r["name"]: r["n"] for r in rows}, "leads_total": leads_n}