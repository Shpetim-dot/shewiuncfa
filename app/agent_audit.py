"""Per-agent audit trail.

Every agent has its own append-only, hash-linked log: what it did, who triggered it, when,
and a hash that chains to the agent's previous entry. This is the evidence a reviewer needs
when asking "what exactly did this agent do last week?" — separate from the organisation-wide
audit log in `main.append_audit`.

Rules:
* One chain per (organisation, agent). Deleting or editing an entry breaks that agent's chain.
* Entries are written by the code paths that create side effects: messages, tool calls,
  approvals, grants, suspensions, model changes, memory writes.
* Logging never breaks the request: failures are swallowed and the API keeps working.
* Reading is scoped to the organisation and requires the same auth as the agent itself.

Endpoints:
    GET  /api/bots/{bot_id}/audit           newest first, paginated with ?limit=&before=
    GET  /api/bots/{bot_id}/audit/verify    walks the chain of this agent
    GET  /api/bots/{bot_id}/audit/export    NDJSON download
"""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app import cfa_core as pf

router = APIRouter()
GENESIS = "GENESIS"

KINDS = ("message", "reply", "tool.call", "tool.requested", "tool.denied", "action", "approval",
         "approval.decided", "memory.write", "memory.verify", "grants.changed", "scopes.changed",
         "status.changed", "model.changed", "created")


def _hash(material: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _prev(con, org_id: str, bot_id: str) -> str:
    row = con.execute("SELECT hash FROM agent_audit WHERE org_id=? AND bot_id=? ORDER BY seq DESC LIMIT 1",
                      (org_id, bot_id)).fetchone()
    return row["hash"] if row else GENESIS


def append(bot_id: str, kind: str, actor: str, summary: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Append one entry to the agent's chain. Returns the entry, or None if logging failed."""
    try:
        org_id, ts, entry_id = pf.org(), pf._m().now(), str(uuid4())
        body = payload or {}
        with pf.db() as con:
            previous = _prev(con, org_id, bot_id)
            material = {"id": entry_id, "org_id": org_id, "bot_id": bot_id, "ts": ts, "kind": kind[:40],
                        "actor": (actor or "")[:120], "summary": (summary or "")[:500],
                        "payload": body, "prev": previous}
            digest = _hash(material)
            con.execute(
                "INSERT INTO agent_audit (id,org_id,bot_id,ts,kind,actor,summary,payload_json,prev_hash,hash) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (entry_id, org_id, bot_id, ts, material["kind"], material["actor"], material["summary"],
                 json.dumps(body, ensure_ascii=False), previous, digest))
        return {**material, "hash": digest}
    except Exception:  # auditing must never break a business request
        return None


def entries(bot_id: str, limit: int = 50, before: str | None = None) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with pf.db() as con:
        org_id = pf.org()
        if before:
            rows = con.execute(
                "SELECT * FROM agent_audit WHERE org_id=? AND bot_id=? AND seq < "
                "(SELECT seq FROM agent_audit WHERE org_id=? AND bot_id=? AND id=?) "
                "ORDER BY seq DESC LIMIT ?", (org_id, bot_id, org_id, bot_id, before, limit)).fetchall()
        else:
            rows = con.execute("SELECT * FROM agent_audit WHERE org_id=? AND bot_id=? ORDER BY seq DESC LIMIT ?",
                               (org_id, bot_id, limit)).fetchall()
        total = con.execute("SELECT COUNT(*) FROM agent_audit WHERE org_id=? AND bot_id=?", (org_id, bot_id)).fetchone()[0]
    out = [{"id": r["id"], "ts": r["ts"], "kind": r["kind"], "actor": r["actor"], "summary": r["summary"],
            "payload": json.loads(r["payload_json"] or "{}"), "prev_hash": r["prev_hash"], "hash": r["hash"]}
           for r in rows]
    return {"agent": bot_id, "total": total, "entries": out}


def verify(bot_id: str) -> dict[str, Any]:
    """Walk this agent's chain and recompute every hash."""
    with pf.db() as con:
        rows = con.execute("SELECT * FROM agent_audit WHERE org_id=? AND bot_id=? ORDER BY seq ASC",
                           (pf.org(), bot_id)).fetchall()
    expected = GENESIS
    checked = 0
    for r in rows:
        material = {"id": r["id"], "org_id": r["org_id"], "bot_id": r["bot_id"], "ts": r["ts"], "kind": r["kind"],
                    "actor": r["actor"], "summary": r["summary"], "payload": json.loads(r["payload_json"] or "{}"),
                    "prev": r["prev_hash"]}
        if r["prev_hash"] != expected or _hash(material) != r["hash"]:
            return {"valid": False, "checked": checked, "failed_entry_id": r["id"]}
        expected, checked = r["hash"], checked + 1
    return {"valid": True, "checked": checked, "head": expected, "agent": bot_id}


def _agent_or_404(bot_id: str) -> dict[str, Any]:
    with pf.db() as con:
        row = con.execute("SELECT id,name FROM bots WHERE id=? AND org_id=?", (bot_id, pf.org())).fetchone()
    if not row:
        raise HTTPException(404, "agent not found")
    return {"id": row["id"], "name": row["name"]}


@router.get("/api/bots/{bot_id}/audit")
def list_audit(bot_id: str, limit: int = 50, before: str | None = None) -> dict[str, Any]:
    agent = _agent_or_404(bot_id)
    data = entries(bot_id, limit, before)
    data["name"] = agent["name"]
    data["integrity"] = verify(bot_id)
    return data


@router.get("/api/bots/{bot_id}/audit/verify")
def verify_audit(bot_id: str) -> dict[str, Any]:
    _agent_or_404(bot_id)
    return verify(bot_id)


@router.get("/api/bots/{bot_id}/audit/export", response_class=PlainTextResponse)
def export_audit(bot_id: str) -> PlainTextResponse:
    _agent_or_404(bot_id)
    with pf.db() as con:
        rows = con.execute("SELECT * FROM agent_audit WHERE org_id=? AND bot_id=? ORDER BY seq ASC",
                           (pf.org(), bot_id)).fetchall()
    lines = [json.dumps({"id": r["id"], "ts": r["ts"], "kind": r["kind"], "actor": r["actor"],
                         "summary": r["summary"], "payload": json.loads(r["payload_json"] or "{}"),
                         "prev_hash": r["prev_hash"], "hash": r["hash"]}, ensure_ascii=False) for r in rows]
    return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""),
                             headers={"Content-Disposition": f"attachment; filename=agent-{bot_id}-audit.ndjson"})


def install(app) -> None:
    app.include_router(router)
