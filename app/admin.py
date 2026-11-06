"""Operations: access keys stored hashed, readiness, backups, retention and data export.

Backups copy the whole database (including encrypted MCP tokens and hashed keys), so they are admin-only and the
encryption key (CFA_SECRET_KEY) must be stored separately from them. The audit log is never purged.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()
BACKUP_NAME = re.compile(r"^(cfa|emergency)-\d{8}-\d{6}\.db$")


# ---------- readiness ----------
@router.get("/api/health/ready")
def ready() -> Response:
    errs = pf.config_errors()
    try:
        with pf.db() as con:
            ok = con.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            con.execute("SELECT 1 FROM bots LIMIT 1").fetchone()
        if not ok:
            errs.append("database integrity check failed")
    except sqlite3.Error:
        errs.append("database is not readable")
    return JSONResponse({"ready": not errs, "errors": errs}, status_code=503 if errs else 200)


# ---------- emergency backup ----------
@router.post("/api/admin/emergency-backup", status_code=201)
def emergency_backup(request: Request) -> dict[str, Any]:
    """One consistent snapshot plus a SHA-256 checksum, for incidents or before a migration.

    Copy the returned file off the host immediately (3-2-1 rule); the endpoint cannot do that
    for you and does not pretend to.
    """
    p = pf.need_admin(request)
    import hashlib
    name = "emergency-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S") + ".db"
    target = _backup_dir() / name
    src = pf._m().connect()
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    pf._m().append_audit("admin.emergency_backup", p["name"], {"file": name, "sha256": digest[:16]})
    return {"name": name, "bytes": target.stat().st_size, "sha256": digest,
            "download": f"/api/admin/backups/{name}",
            "note": "Copy this file off the host now; keep three copies, two media, one offsite."}


# ---------- metrics ----------
@router.get("/api/admin/metrics")
def metrics(request: Request) -> dict[str, Any]:
    """Cheap operational snapshot: request budget, database size, table counts, key numbers.

    No external system is contacted and nothing is invented: every value is read from the
    database that serves the requests.
    """
    pf.need_admin(request)
    from app import ratelimit
    org = pf.org()
    with pf.db() as con:
        size = Path(pf._m().DB_PATH).stat().st_size if Path(pf._m().DB_PATH).exists() else 0

        def one(sql: str, *params) -> int:
            return con.execute(sql, params).fetchone()[0]

        counts = {
            "agents": one("SELECT COUNT(*) FROM bots WHERE org_id=?", org),
            "notes": one("SELECT COUNT(*) FROM notes WHERE org_id=?", org),
            "calls": one("SELECT COUNT(*) FROM calls WHERE org_id=?", org),
            "approvals_pending": one("SELECT COUNT(*) FROM approval_requests WHERE status='pending' AND org_id=?", org),
            "audit_events": one("SELECT COUNT(*) FROM audit_events WHERE org_id=?", org),
            "agent_audit_entries": one("SELECT COUNT(*) FROM agent_audit WHERE org_id=?", org),
            "tool_calls": one("SELECT COUNT(*) FROM pending_calls WHERE org_id=?", org),
            "runtime_queued": one("SELECT COUNT(*) FROM runtime_runs WHERE status='queued' AND org_id=?", org),
            "runtime_failed": one("SELECT COUNT(*) FROM runtime_runs WHERE status='failed' AND org_id=?", org),
            "users": one("SELECT COUNT(*) FROM users WHERE org_id=?", org),
            "llm_calls_30d": one("SELECT COUNT(*) FROM llm_usage WHERE org_id=?", org),
        }
    return {"org_id": org, "database_bytes": size, "database_mb": round(size / 1_048_576, 2),
            "counts": counts, "rate_limit": ratelimit.usage(org)}


# ---------- access keys ----------
class KeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    role: str = Field(pattern="^(admin|member|viewer)$")


@router.get("/api/admin/keys")
def list_keys(request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    with pf.db() as con:
        rows = con.execute("SELECT id,name,role,created_by,created_at,last_used,revoked FROM api_keys WHERE org_id=? ORDER BY created_at DESC",
                           (pf.org(),)).fetchall()
    return {"keys": [dict(r) for r in rows], "env_keys": len(pf._keys()), "note": "Tokens are shown once when created and stored only as a hash."}


@router.post("/api/admin/keys", status_code=201)
def create_key(item: KeyIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    token = "cfa_" + secrets.token_urlsafe(32)
    kid = uuid4().hex[:10]
    with pf.db() as con:
        con.execute("INSERT INTO api_keys (id,name,role,token_hash,created_by,created_at,revoked,org_id) VALUES (?,?,?,?,?,?,0,?)",
                    (kid, item.name.strip(), item.role, pf._hash(token), p["name"], pf._m().now(), pf.org()))
    pf._m().append_audit("key.created", p["name"], {"id": kid, "name": item.name.strip(), "role": item.role})
    return {"id": kid, "name": item.name.strip(), "role": item.role, "token": token, "warning": "Copy this token now. It cannot be shown again."}


@router.delete("/api/admin/keys/{kid}")
def revoke_key(kid: str, request: Request) -> dict[str, str]:
    p = pf.need_admin(request)
    with pf.db() as con:
        r = con.execute("SELECT role,revoked FROM api_keys WHERE id=? AND org_id=?", (kid, pf.org())).fetchone()
        if not r:
            raise HTTPException(404, "key not found")
        env_admins = sum(1 for v in pf._keys().values() if v["role"] == "admin")
        db_admins = con.execute("SELECT COUNT(*) FROM api_keys WHERE role='admin' AND revoked=0 AND id<>? AND org_id=?",
                                (kid, pf.org())).fetchone()[0]
        if r["role"] == "admin" and not r["revoked"] and env_admins + db_admins == 0:
            raise HTTPException(409, "this is the last admin key; create another admin key first")
        con.execute("UPDATE api_keys SET revoked=1 WHERE id=? AND org_id=?", (kid, pf.org()))
    pf._m().append_audit("key.revoked", p["name"], {"id": kid})
    return {"status": "revoked"}


# ---------- backups ----------
def _backup_dir() -> Path:
    d = Path(pf._m().DB_PATH).parent / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _files() -> list[Path]:
    return sorted((f for f in _backup_dir().iterdir() if BACKUP_NAME.match(f.name)), reverse=True)


@router.post("/api/admin/backup", status_code=201)
def backup(request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    name = "cfa-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S") + ".db"
    target = _backup_dir() / name
    src = pf._m().connect()
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)  # consistent snapshot even while the app is writing
    finally:
        dst.close()
        src.close()
    keep = int(os.getenv("CFA_BACKUP_KEEP", "14"))
    for old in _files()[keep:]:
        old.unlink(missing_ok=True)
    pf._m().append_audit("admin.backup", p["name"], {"file": name, "bytes": target.stat().st_size})
    return {"name": name, "bytes": target.stat().st_size, "kept": min(len(_files()), keep)}


@router.get("/api/admin/backups")
def backups(request: Request) -> list[dict[str, Any]]:
    pf.need_admin(request)
    return [{"name": f.name, "bytes": f.stat().st_size} for f in _files()]


@router.get("/api/admin/backups/{name}")
def download_backup(name: str, request: Request) -> FileResponse:
    p = pf.need_admin(request)
    if not BACKUP_NAME.match(name) or not (_backup_dir() / name).exists():
        raise HTTPException(404, "backup not found")
    pf._m().append_audit("admin.backup.downloaded", p["name"], {"file": name})
    return FileResponse(_backup_dir() / name, filename=name, media_type="application/octet-stream")


# ---------- organisation deletion (GDPR art. 17) ----------
@router.delete("/api/org")
def delete_organisation(confirm: str, request: Request) -> dict[str, Any]:
    """Delete the caller's organisation and everything that belongs to it.

    Requires the organisation slug as `?confirm=<slug>` (mistake guard), the owner role, and it
    records the deletion in `deletion_log` — the audit trail of the deleted tenant cannot stay
    readable, so the deletion itself is logged outside of it.
    """
    from app import auth
    principal = pf._principal(request)
    if auth.rank(principal.get("role")) < auth.rank("owner"):
        raise HTTPException(403, "only the owner can delete the organisation")
    org_id = principal.get("org_id")
    if not org_id:
        raise HTTPException(400, "this session has no organisation")
    with pf.db() as con:
        org = con.execute("SELECT id,slug,name FROM orgs WHERE id=?", (org_id,)).fetchone()
        if not org:
            raise HTTPException(404, "organisation not found")
        if (confirm or "").strip().lower() != org["slug"]:
            raise HTTPException(422, "confirmation does not match the organisation slug")
        counts: dict[str, int] = {}
        for table in pf.TENANT_TABLES:
            cols = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
            if "org_id" in cols:
                counts[table] = con.execute(f"DELETE FROM {table} WHERE org_id=?", (org_id,)).rowcount
        # sessions and tokens reference users, so they go first (foreign keys are enforced)
        for table in ("sessions", "auth_tokens"):
            try:
                counts[table] = con.execute(
                    f"DELETE FROM {table} WHERE user_id IN (SELECT id FROM users WHERE org_id=?)", (org_id,)).rowcount
            except Exception:
                pass
        for table in ("org_billing", "org_usage", "org_settings", "org_apps", "org_events",
                      "rate_limits", "announcements", "invitations", "users"):
            try:
                counts[table] = con.execute(f"DELETE FROM {table} WHERE org_id=?", (org_id,)).rowcount
            except Exception:
                pass
        con.execute("DELETE FROM orgs WHERE id=?", (org_id,))
        con.execute("INSERT INTO deletion_log (id,org_id,slug,actor,deleted_at,counts_json) VALUES (?,?,?,?,?,?)",
                    (str(uuid4()), org_id, org["slug"], principal["name"], pf._m().now(),
                     json.dumps(counts, sort_keys=True)))
    return {"deleted": True, "org_id": org_id, "slug": org["slug"],
            "records": {k: v for k, v in counts.items() if v}, "note": "Sessions are gone with the users."}


# ---------- retention and export ----------
class RetentionIn(BaseModel):
    days: int = Field(ge=7, le=3650)


@router.post("/api/admin/retention")
def retention(item: RetentionIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    from app import billing
    if billing.enabled():
        with pf.db() as con:
            allowed = billing.limits_for(billing.current_plan(con))["audit_days"]
        if item.days > allowed:
            raise HTTPException(402, {"code": "limit_reached", "metric": "audit_days", "limit": allowed,
                                      "message": f"Your plan keeps {allowed} days of activity. Upgrade for a longer retention."})
    cutoff = (datetime.fromisoformat(pf._m().now()) - timedelta(days=item.days)).isoformat()
    spec = [("agent_activity", "ts"), ("brain_events", "ts"), ("bot_messages", "created_at"), ("calls", "created_at"), ("research", "created_at")]
    counts: dict[str, int] = {}
    with pf.db() as con:
        for tbl, col in spec:
            counts[tbl] = con.execute(f"DELETE FROM {tbl} WHERE {col} < ? AND org_id = ?", (cutoff, pf.org())).rowcount
    pf._m().append_audit("admin.retention", p["name"], {"days": item.days, "deleted": counts})
    return {"days": item.days, "deleted": counts, "note": "The audit log is never purged."}


@router.get("/api/admin/export")
def export(request: Request) -> JSONResponse:
    """JSON export of the caller's organisation (GDPR-style data portability)."""
    p = pf.need_admin(request)
    org = pf.org()

    def rows(con, q: str) -> list[dict[str, Any]]:
        return [dict(r) for r in con.execute(q, (org,))]

    with pf.db() as con:
        bundle = {"exported_at": pf._m().now(), "version": pf.VERSION, "org_id": org,
                  "bots": rows(con, "SELECT id,name,role,system,color,model,scopes,spaces,template,icon,team,status,criticality,source,trust,source_ref,owner,created_at FROM bots WHERE org_id=?"),
                  "teams": rows(con, "SELECT * FROM teams WHERE org_id=?"),
                  "notes": rows(con, "SELECT * FROM notes WHERE org_id=?"),
                  "note_versions": rows(con, "SELECT * FROM note_versions WHERE org_id=?"),
                  "grants": rows(con, "SELECT * FROM grants WHERE org_id=?"),
                  "calls": rows(con, "SELECT * FROM calls WHERE org_id=?"),
                  "research": rows(con, "SELECT * FROM research WHERE org_id=?"),
                  "mcp_servers": rows(con, "SELECT id,name,url,tools,created_by,created_at FROM mcp_servers WHERE org_id=?")}
    pf._m().append_audit("admin.export", p["name"], {"notes": len(bundle["notes"]), "bots": len(bundle["bots"])})
    return JSONResponse(bundle, headers={"Content-Disposition": "attachment; filename=cfa-export.json"})
