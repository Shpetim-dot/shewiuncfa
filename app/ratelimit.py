"""Durable, per-organisation rate limiting.

The in-process limiter in `cfa_core` protects individual IPs against bursts and dies with the
process. This module is the production gate: counters live in SQLite, are keyed by organisation
and minute, and survive restarts and multiple workers of the same deployment.

Limits follow the plan (`app/billing.py`). With `CFA_BILLING` off (self-hosted) the limit is
`CFA_RATELIMIT_DEFAULT` (default 10 000 requests/minute) so a local install is never throttled
by accident. `CFA_RATELIMIT=off` disables it completely.

Cost: one UPSERT and one SELECT per request on a tiny table; windows older than a few minutes are
pruned opportunistically.
"""
from __future__ import annotations

import os
import time
from typing import Any

from fastapi import HTTPException

from app import cfa_core as pf

TABLE = """CREATE TABLE IF NOT EXISTS rate_limits(
    org_id TEXT NOT NULL, window INTEGER NOT NULL, n INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(org_id, window))"""

DEFAULT_LIMIT = 10_000
# Requests per minute and organisation; a plan is a commercial promise, not a suggestion.
PLAN_LIMITS = {"free": 120, "starter": 600, "professional": 2_000, "enterprise": 10_000}

_ensured: set[str] = set()
_plan_cache: dict[str, tuple[float, str]] = {}


def enabled() -> bool:
    return os.getenv("CFA_RATELIMIT", "on").lower() not in ("off", "0", "false")


def _con():
    con = pf.db()
    key = str(pf._m().DB_PATH)
    if key not in _ensured:
        con.execute(TABLE)
        con.commit()
        _ensured.add(key)
    return con


def _plan(org_id: str) -> str:
    cached = _plan_cache.get(org_id)
    now = time.monotonic()
    if cached and now - cached[0] < 60:
        return cached[1]
    try:
        from app import billing
        with pf.db() as con:
            plan = billing.current_plan(con) if pf.org() == org_id else "free"
    except Exception:
        plan = "free"
    _plan_cache[org_id] = (now, plan)
    return plan


def limit_for(org_id: str) -> int:
    if not os.getenv("CFA_BILLING") == "on":
        return int(os.getenv("CFA_RATELIMIT_DEFAULT", str(DEFAULT_LIMIT)))
    return PLAN_LIMITS.get(_plan(org_id), PLAN_LIMITS["free"])


def reset_cache() -> None:
    _plan_cache.clear()


def check(org_id: str | None) -> dict[str, Any] | None:
    """Count one request. Returns None when allowed, the 429 body when the limit is hit."""
    if not enabled():
        return None
    org = org_id or pf.DEFAULT_ORG
    limit = limit_for(org)
    window = int(time.time() // 60)
    with _con() as con:
        if window % 30 == 0:  # opportunistic pruning, ~twice per hour
            con.execute("DELETE FROM rate_limits WHERE window < ?", (window - 5,))
        con.execute("INSERT INTO rate_limits (org_id,window,n) VALUES (?,?,1) "
                    "ON CONFLICT(org_id, window) DO UPDATE SET n = n + 1", (org, window))
        used = con.execute("SELECT n FROM rate_limits WHERE org_id=? AND window=?", (org, window)).fetchone()["n"]
    if used > limit:
        return {"code": "rate_limited", "limit": limit, "window_seconds": 60,
                "message": f"Rate limit of {limit} requests per minute reached for this workspace."}
    return None


def usage(org_id: str) -> dict[str, Any]:
    """Current window usage, for the operator metrics endpoint."""
    window = int(time.time() // 60)
    with _con() as con:
        row = con.execute("SELECT n FROM rate_limits WHERE org_id=? AND window=?", (org_id, window)).fetchone()
    return {"org_id": org_id, "window": window, "used": row["n"] if row else 0, "limit": limit_for(org_id)}
