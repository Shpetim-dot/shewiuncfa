"""Model gateway: provider registry (keys encrypted at rest), usage and cost records, versioned prices, fallbacks and a monthly budget cap.

Costs are never invented: a cost is stored only when a price record for that provider and model exists. Otherwise it is NULL and shown as unknown.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()
RESERVED = {"hf", "openai", "default"}
FALLBACK_CODES = (402, 429, 502)  # only real provider failures trigger a configured fallback; a missing key never does


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _setting(con, key: str) -> Any:
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else None


def _set(con, key: str, value: Any) -> None:
    con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))


# ---------- provider registry ----------
def registered(pid: str) -> tuple[str, str | None] | None:
    """(base_url, api_key) of a registered provider, or None. The key is decrypted here and never leaves the process."""
    with pf.db() as con:
        r = con.execute("SELECT base_url,key_enc FROM providers WHERE id=?", (pid,)).fetchone()
    if not r:
        return None
    key = None
    if r["key_enc"]:
        from app import mcp_apps
        f = mcp_apps._fernet()
        if not f:
            return r["base_url"], None  # without CFA_SECRET_KEY a stored key cannot be used
        try:
            key = f.decrypt(r["key_enc"].encode()).decode()
        except Exception:
            key = None
    return r["base_url"], key


class ProviderIn(BaseModel):
    id: str = Field(pattern="^[a-z0-9][a-z0-9-]{1,29}$")
    name: str = Field(default="", max_length=60)
    base_url: str = Field(max_length=300)
    api_key: str = Field(min_length=8, max_length=400)


@router.get("/api/providers")
def list_providers() -> list[dict[str, Any]]:
    with pf.db() as con:
        rows = con.execute("SELECT id,name,base_url,key_enc,last_test,last_status,created_at FROM providers ORDER BY id").fetchall()
    return [{"id": r["id"], "name": r["name"] or r["id"], "base_url": r["base_url"], "has_key": bool(r["key_enc"]), "last_test": r["last_test"],
             "status": r["last_status"] or "untested", "model_prefix": r["id"] + ":"} for r in rows]


@router.post("/api/providers", status_code=201)
def add_provider(item: ProviderIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    from app import mcp_apps
    if item.id in RESERVED:
        raise HTTPException(422, "this id is reserved")
    mcp_apps.check_url(item.base_url)  # SSRF guard: https only, no private or internal addresses
    f = mcp_apps._fernet()
    if not f:
        raise HTTPException(409, "set CFA_SECRET_KEY first: provider keys are stored encrypted")
    with pf.db() as con:
        if con.execute("SELECT 1 FROM providers WHERE id=?", (item.id,)).fetchone():
            raise HTTPException(409, "a provider with this id exists")
        con.execute("INSERT INTO providers (id,name,base_url,key_enc,created_by,created_at) VALUES (?,?,?,?,?,?)",
                    (item.id, item.name, item.base_url.rstrip("/"), f.encrypt(item.api_key.encode()).decode(), p["name"], _now()))
    pf._m().append_audit("provider.added", p["name"], {"id": item.id, "base_url": item.base_url})  # the key is never logged
    return {"id": item.id, "model_prefix": item.id + ":", "status": "untested"}


class ProviderTest(BaseModel):
    model: str = Field(min_length=1, max_length=120)


@router.post("/api/providers/{pid}/test")
async def test_provider(pid: str, item: ProviderTest, request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    if not registered(pid):
        raise HTTPException(404, "provider not found")
    status, detail = "ok", ""
    try:
        await pf.llm("Reply with the single word: ok", "ping", f"{pid}:{item.model}", {"kind": "test"})
    except HTTPException as e:
        status, detail = "failed", str(e.detail)
    with pf.db() as con:
        con.execute("UPDATE providers SET last_test=?, last_status=? WHERE id=?", (_now(), status, pid))
    return {"id": pid, "model": item.model, "status": status, "detail": detail}


@router.delete("/api/providers/{pid}")
def delete_provider(pid: str, request: Request) -> dict[str, str]:
    p = pf.need_admin(request)
    with pf.db() as con:
        if not con.execute("DELETE FROM providers WHERE id=?", (pid,)).rowcount:
            raise HTTPException(404, "provider not found")
    pf._m().append_audit("provider.removed", p["name"], {"id": pid})
    return {"removed": pid}


# ---------- prices (versioned, with a source) ----------
class PriceIn(BaseModel):
    provider: str = Field(max_length=40)
    model: str = Field(max_length=120)
    input_per_mtok: float = Field(ge=0)
    output_per_mtok: float = Field(ge=0)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")
    effective_from: str | None = Field(default=None, max_length=40)
    source: str = Field(min_length=4, max_length=300)  # where the price comes from; a price without a source is rejected


@router.put("/api/prices", status_code=201)
def add_price(item: PriceIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    pid = str(uuid4())
    with pf.db() as con:
        con.execute("INSERT INTO model_prices VALUES (?,?,?,?,?,?,?,?,?)", (pid, item.provider, item.model, item.input_per_mtok, item.output_per_mtok, item.currency,
                                                                           item.effective_from or _now(), item.source, p["name"]))
    pf._m().append_audit("price.added", p["name"], {"id": pid, "provider": item.provider, "model": item.model})
    return {"id": pid}


@router.get("/api/prices")
def list_prices() -> list[dict[str, Any]]:
    with pf.db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM model_prices ORDER BY provider, model, effective_from DESC")]


def price_for(con, provider: str, model: str, at: str):
    return con.execute("SELECT * FROM model_prices WHERE provider=? AND model=? AND effective_from<=? ORDER BY effective_from DESC LIMIT 1", (provider, model, at)).fetchone()


def cost_of(price, tokens_in: int, tokens_out: int) -> float | None:
    if not price:
        return None
    return round(tokens_in / 1e6 * price["input_per_mtok"] + tokens_out / 1e6 * price["output_per_mtok"], 8)


def record_usage(*, kind: str, bot_id: str | None, provider: str, model: str, requested: str, fallback: bool, tokens_in: int | None, tokens_out: int | None,
                 latency_ms: int, status: str, error: str = "") -> None:
    ts = _now()
    try:
        with pf.db() as con:
            price = price_for(con, provider, model, ts) if tokens_in is not None else None
            cost = cost_of(price, tokens_in or 0, tokens_out or 0)
            con.execute("INSERT INTO llm_usage VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                str(uuid4()), ts, provider, model, requested, int(fallback), kind, bot_id, tokens_in, tokens_out, latency_ms, status, error[:200],
                cost, price["currency"] if price else None))
    except Exception:  # usage bookkeeping must never break a model call
        pass


# ---------- fallbacks and budget ----------
def fallbacks(model: str | None) -> list[str]:
    with pf.db() as con:
        lst = _setting(con, "fallback_models") or []
    return [m for m in lst if m != model][:3]


def check_budget() -> None:
    with pf.db() as con:
        cap = _setting(con, "monthly_cap")
        if not cap:
            return
        start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        spent = con.execute("SELECT COALESCE(SUM(cost),0) FROM llm_usage WHERE ts>=? AND cost IS NOT NULL", (start,)).fetchone()[0]
    if spent >= cap["amount"]:
        raise HTTPException(402, f"The monthly AI budget of {cap['amount']} {cap['currency']} is used up. An admin can raise it under Usage.")


class FallbackIn(BaseModel):
    models: list[str] = Field(max_length=3)


@router.put("/api/fallbacks")
def set_fallbacks(item: FallbackIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    models = [m.strip()[:120] for m in item.models if m.strip()]
    with pf.db() as con:
        _set(con, "fallback_models", models)
    pf._m().append_audit("fallbacks.changed", p["name"], {"models": models})
    return {"models": models, "note": "Used only after a provider failure; every use is recorded in Usage as a fallback."}


class BudgetIn(BaseModel):
    amount: float | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", pattern="^[A-Z]{3}$")


@router.put("/api/usage/budget")
def set_budget(item: BudgetIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    with pf.db() as con:
        _set(con, "monthly_cap", {"amount": item.amount, "currency": item.currency} if item.amount else None)
    pf._m().append_audit("budget.changed", p["name"], {"amount": item.amount, "currency": item.currency})
    return {"amount": item.amount, "currency": item.currency}


# ---------- usage report ----------
@router.get("/api/usage")
def usage(days: int = 30) -> dict[str, Any]:
    days = max(1, min(days, 365))
    since = (datetime.now(timezone.utc).timestamp() - days * 86400)
    since_iso = datetime.fromtimestamp(since, timezone.utc).isoformat()
    with pf.db() as con:
        rows = con.execute("""SELECT provider, model, COUNT(*) calls, SUM(status='ok') ok, SUM(status!='ok') errors, SUM(COALESCE(tokens_in,0)) tin, SUM(COALESCE(tokens_out,0)) tout,
            AVG(latency_ms) latency, SUM(cost) cost, SUM(status='ok' AND cost IS NULL) unknown_cost, SUM(fallback) fallbacks, MAX(currency) currency
            FROM llm_usage WHERE ts>=? GROUP BY provider, model ORDER BY calls DESC""", (since_iso,)).fetchall()
        kinds = con.execute("SELECT kind, COUNT(*) n FROM llm_usage WHERE ts>=? GROUP BY kind", (since_iso,)).fetchall()
        cap = _setting(con, "monthly_cap")
        fb = _setting(con, "fallback_models") or []
        start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        spent = con.execute("SELECT COALESCE(SUM(cost),0) FROM llm_usage WHERE ts>=? AND cost IS NOT NULL", (start,)).fetchone()[0]
    models = [{"provider": r["provider"], "model": r["model"], "calls": r["calls"], "ok": r["ok"], "errors": r["errors"], "tokens_in": r["tin"], "tokens_out": r["tout"],
               "avg_latency_ms": round(r["latency"] or 0), "cost": r["cost"], "currency": r["currency"], "calls_with_unknown_cost": r["unknown_cost"], "fallback_calls": r["fallbacks"]} for r in rows]
    return {"days": days, "models": models, "by_kind": {r["kind"]: r["n"] for r in kinds},
            "cost_is_partial": any(m["calls_with_unknown_cost"] for m in models),
            "note": "Tokens come from the provider's usage data. Cost is shown only where a price record exists; otherwise it is unknown.",
            "budget": {"monthly_cap": cap, "spent_this_month_known_cost": round(spent, 6)}, "fallback_models": fb}
