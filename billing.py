"""Plans, monthly usage limits, Stripe subscriptions, leads and funnel events.

Billing is OFF unless CFA_BILLING=on, so self-hosted and development installs stay unlimited.
The plan can be fixed by the operator with CFA_PLAN (for pilots and invoiced customers) or follows Stripe.
Stripe is untested against the live service here: use test mode and `stripe listen` first.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import time
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
    "free": {"name": "Free", "price_eur": 0, "tagline": "Try it with your own notes", "limits": {"messages": 50, "calls": 3, "research": 3, "uploads": 5, "agents": 4, "mcp_servers": 0}},
    "pro": {"name": "Pro", "price_eur": 19, "tagline": "For one person running real work", "limits": {"messages": 1500, "calls": 60, "research": 60, "uploads": 100, "agents": 15, "mcp_servers": 3}},
    "team": {"name": "Team", "price_eur": 99, "tagline": "For a small team with live tools", "limits": {"messages": 10000, "calls": 400, "research": 400, "uploads": 1000, "agents": 50, "mcp_servers": 15}},
    "pilot": {"name": "Pilot", "price_eur": None, "tagline": "Invoiced, set up with you", "limits": {"messages": BIG, "calls": BIG, "research": BIG, "uploads": BIG, "agents": 200, "mcp_servers": 50}},
}
LABEL = {"messages": "agent messages", "calls": "council calls", "research": "deep research runs", "uploads": "file uploads", "agents": "agents", "mcp_servers": "live MCP servers"}
MONTHLY = ("messages", "calls", "research", "uploads")


def enabled() -> bool:
    return os.getenv("CFA_BILLING") == "on"


CORE_AGENTS = ("strategist", "skeptic", "builder", "chair")


def agent_count(con) -> int:
    """Agents you created or imported. The four built-in council agents are free on every plan."""
    return con.execute("SELECT COUNT(*) FROM bots WHERE id NOT IN (?,?,?,?)", CORE_AGENTS).fetchone()[0]


def current_plan(con) -> str:
    forced = os.getenv("CFA_PLAN")
    if forced in PLANS:
        return forced
    r = con.execute("SELECT plan,status FROM billing WHERE id=1").fetchone()
    return r["plan"] if r and r["status"] in ("active", "trialing", "past_due") and r["plan"] in PLANS else "free"


def _deny(metric: str, plan: str, limit: int, used: int) -> HTTPException:
    return HTTPException(402, {"code": "limit_reached", "metric": metric, "label": LABEL[metric], "limit": limit, "used": used, "plan": plan,
                               "message": f"You reached the {PLANS[plan]['name']} plan limit for {LABEL[metric]} ({limit}). Upgrade to continue."})


def use(metric: str, amount: int = 1) -> None:
    """Count one unit of a monthly metric; raises 402 when the plan limit is reached."""
    if not enabled():
        return
    period = pf._m().now()[:7]
    with pf.db() as con:
        plan = current_plan(con)
        limit = PLANS[plan]["limits"][metric]
        row = con.execute("SELECT n FROM usage WHERE period=? AND metric=?", (period, metric)).fetchone()
        used = row["n"] if row else 0
        if used + amount > limit:
            raise _deny(metric, plan, limit, used)
        con.execute("INSERT INTO usage VALUES (?,?,?) ON CONFLICT(period, metric) DO UPDATE SET n = n + ?", (period, metric, amount, amount))


def check_count(metric: str, current: int, adding: int = 1) -> None:
    if not enabled():
        return
    with pf.db() as con:
        plan = current_plan(con)
    if current + adding > PLANS[plan]["limits"][metric]:
        raise _deny(metric, plan, PLANS[plan]["limits"][metric], current)


@router.get("/api/public")
def public_info() -> dict[str, Any]:
    """What the public pages (/welcome, /trust) may show: prices, contacts and the version. No workspace data."""
    return {"version": pf.VERSION, "contact": os.getenv("CFA_CONTACT_URL", ""), "security_contact": os.getenv("CFA_SECURITY_CONTACT", ""),
            "plans": [{"id": k, "name": v["name"], "price_eur": v["price_eur"], "tagline": v["tagline"], "limits": v["limits"]} for k, v in PLANS.items()]}


@router.get("/api/billing")
def billing() -> dict[str, Any]:
    period = pf._m().now()[:7]
    with pf.db() as con:
        plan = current_plan(con)
        row = con.execute("SELECT * FROM billing WHERE id=1").fetchone()
        usage = {r["metric"]: r["n"] for r in con.execute("SELECT metric,n FROM usage WHERE period=?", (period,))}
        usage["agents"] = agent_count(con)
        usage["mcp_servers"] = con.execute("SELECT COUNT(*) FROM mcp_servers").fetchone()[0]
    stripe_ready = bool(os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_PRICE_PRO") and os.getenv("STRIPE_PRICE_TEAM"))
    return {"enabled": enabled(), "plan": plan, "plan_name": PLANS[plan]["name"], "plan_locked": bool(os.getenv("CFA_PLAN")), "status": row["status"] if row else "active",
            "period_end": row["period_end"] if row else None, "limits": PLANS[plan]["limits"], "usage": {k: usage.get(k, 0) for k in LABEL}, "labels": LABEL,
            "plans": [{"id": k, "name": v["name"], "price_eur": v["price_eur"], "tagline": v["tagline"], "limits": v["limits"]} for k, v in PLANS.items()],
            "checkout": stripe_ready, "portal": bool(row and row["customer_id"] and os.getenv("STRIPE_SECRET_KEY")), "contact": os.getenv("CFA_CONTACT_URL", "")}


# ---------- Stripe ----------
async def _stripe(path: str, data: dict[str, str]) -> dict[str, Any]:
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        raise HTTPException(503, "Stripe is not configured on this deployment")
    try:
        async with httpx.AsyncClient(transport=STRIPE_TRANSPORT, timeout=20, base_url="https://api.stripe.com") as c:
            r = await c.post(path, data=data, headers={"Authorization": f"Bearer {key}"})
    except httpx.HTTPError:
        raise HTTPException(502, "Stripe could not be reached")
    if r.status_code >= 400:
        raise HTTPException(502, "Stripe rejected the request")
    return r.json()


def _base(request: Request) -> str:
    return (os.getenv("APP_URL") or str(request.base_url)).rstrip("/")


class CheckoutIn(BaseModel):
    plan: str = Field(pattern="^(pro|team)$")


@router.post("/api/billing/checkout")
async def checkout(item: CheckoutIn, request: Request) -> dict[str, str]:
    p = pf.need_admin(request)
    price = os.getenv(f"STRIPE_PRICE_{item.plan.upper()}")
    if not price:
        raise HTTPException(503, "this plan has no Stripe price configured")
    base = _base(request)
    with pf.db() as con:
        row = con.execute("SELECT customer_id FROM billing WHERE id=1").fetchone()
    data = {"mode": "subscription", "line_items[0][price]": price, "line_items[0][quantity]": "1", "success_url": base + "/?billing=success", "cancel_url": base + "/?billing=cancel",
            "client_reference_id": "workspace", "metadata[plan]": item.plan, "subscription_data[metadata][plan]": item.plan, "allow_promotion_codes": "true"}
    if row and row["customer_id"]:
        data["customer"] = row["customer_id"]
    url = (await _stripe("/v1/checkout/sessions", data)).get("url", "")
    if not url.startswith("https://checkout.stripe.com/"):
        raise HTTPException(502, "unexpected checkout address")
    pf._m().append_audit("billing.checkout_started", p["name"], {"plan": item.plan})
    return {"url": url}


@router.post("/api/billing/portal")
async def portal(request: Request) -> dict[str, str]:
    pf.need_admin(request)
    with pf.db() as con:
        row = con.execute("SELECT customer_id FROM billing WHERE id=1").fetchone()
    if not row or not row["customer_id"]:
        raise HTTPException(409, "there is no paid subscription yet")
    url = (await _stripe("/v1/billing_portal/sessions", {"customer": row["customer_id"], "return_url": _base(request)})).get("url", "")
    if not url.startswith("https://billing.stripe.com/"):
        raise HTTPException(502, "unexpected portal address")
    return {"url": url}


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
    for plan in ("pro", "team"):
        if price_id and price_id == os.getenv(f"STRIPE_PRICE_{plan.upper()}"):
            return plan
    return None


def _set_billing(con, **kw: Any) -> None:
    con.execute("INSERT OR IGNORE INTO billing (id,plan,status,updated_at) VALUES (1,'free','active',?)", (pf._m().now(),))
    for k, v in kw.items():
        con.execute(f"UPDATE billing SET {k}=?, updated_at=? WHERE id=1", (v, pf._m().now()))


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
        if kind == "checkout.session.completed" and obj.get("mode") == "subscription":
            plan = (obj.get("metadata") or {}).get("plan")
            if plan in ("pro", "team"):
                _set_billing(con, plan=plan, status="active", customer_id=obj.get("customer"), subscription_id=obj.get("subscription"))
                changed = plan
        elif kind in ("customer.subscription.updated", "customer.subscription.created"):
            price = (((obj.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get("id")
            plan = _price_to_plan(price) or (obj.get("metadata") or {}).get("plan")
            if plan in ("pro", "team"):
                _set_billing(con, plan=plan, status=obj.get("status", "active"), customer_id=obj.get("customer"), subscription_id=obj.get("id"),
                             period_end=str(obj.get("current_period_end") or ""))
                changed = plan
        elif kind == "customer.subscription.deleted":
            _set_billing(con, plan="free", status="canceled")
            changed = "free"
        elif kind == "invoice.payment_failed":
            _set_billing(con, status="past_due")
            changed = "past_due"
    if changed:
        pf._m().append_audit("billing.plan_changed", "stripe", {"event": ev.get("type"), "to": changed})
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
        con.execute("INSERT INTO leads VALUES (?,?,?,?,?,?,?)", (uuid4().hex[:10], pf._m().now(), item.name.strip(), item.email.strip().lower(), item.company.strip(), item.message.strip(), item.source))
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
        return [dict(r) for r in con.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT 200")]


class EventIn(BaseModel):
    name: str = Field(max_length=30)


@router.post("/api/events", status_code=201)
def event(item: EventIn) -> dict[str, bool]:
    if item.name not in EVENTS:
        raise HTTPException(422, "unknown event")
    day = pf._m().now()[:10]
    with pf.db() as con:
        con.execute("INSERT INTO events VALUES (?,?,1) ON CONFLICT(day, name) DO UPDATE SET n = n + 1", (day, item.name))
    return {"ok": True}


@router.get("/api/events/summary")
def events_summary(request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    with pf.db() as con:
        rows = con.execute("SELECT name, SUM(n) AS n FROM events WHERE day >= date('now','-30 day') GROUP BY name").fetchall()
        leads_n = con.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    return {"last_30_days": {r["name"]: r["n"] for r in rows}, "leads_total": leads_n}
