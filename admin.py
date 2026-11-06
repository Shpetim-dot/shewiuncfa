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
BACKUP_NAME = re.compile(r"^cfa-\d{8}-\d{6}\.db$")


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


# ---------- access keys ----------
class KeyIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    role: str = Field(pattern="^(admin|member|viewer)$")


@router.get("/api/admin/keys")
def list_keys(request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    with pf.db() as con:
        rows = con.execute("SELECT id,name,role,created_by,created_at,last_used,revoked FROM api_keys ORDER BY created_at DESC").fetchall()
    return {"keys": [dict(r) for r in rows], "env_keys": len(pf._keys()), "note": "Tokens are shown once when created and stored only as a hash."}


@router.post("/api/admin/keys", status_code=201)
def create_key(item: KeyIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    token = "cfa_" + secrets.token_urlsafe(32)
    kid = uuid4().hex[:10]
    with pf.db() as con:
        con.execute("INSERT INTO api_keys (id,name,role,token_hash,created_by,created_at,revoked) VALUES (?,?,?,?,?,?,0)", (kid, item.name.strip(), item.role, pf._hash(token), p["name"], pf._m().now()))
    pf._m().append_audit("key.created", p["name"], {"id": kid, "name": item.name.strip(), "role": item.role})
    return {"id": kid, "name": item.name.strip(), "role": item.role, "token": token, "warning": "Copy this token now. It cannot be shown again."}


@router.delete("/api/admin/keys/{kid}")
def revoke_key(kid: str, request: Request) -> dict[str, str]:
    p = pf.need_admin(request)
    with pf.db() as con:
        r = con.execute("SELECT role,revoked FROM api_keys WHERE id=?", (kid,)).fetchone()
        if not r:
            raise HTTPException(404, "key not found")
        env_admins = sum(1 for v in pf._keys().values() if v["role"] == "admin")
        db_admins = con.execute("SELECT COUNT(*) FROM api_keys WHERE role='admin' AND revoked=0 AND id<>?", (kid,)).fetchone()[0]
        if r["role"] == "admin" and not r["revoked"] and env_admins + db_admins == 0:
            raise HTTPException(409, "this is the last admin key; create another admin key first")
        con.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (kid,))
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


# ---------- retention and export ----------
class RetentionIn(BaseModel):
    days: int = Field(ge=7, le=3650)


@router.post("/api/admin/retention")
def retention(item: RetentionIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    cutoff = (datetime.fromisoformat(pf._m().now()) - timedelta(days=item.days)).isoformat()
    spec = [("agent_activity", "ts"), ("brain_events", "ts"), ("bot_messages", "created_at"), ("calls", "created_at"), ("research", "created_at")]
    counts: dict[str, int] = {}
    with pf.db() as con:
        for tbl, col in spec:
            counts[tbl] = con.execute(f"DELETE FROM {tbl} WHERE {col} < ?", (cutoff,)).rowcount
    pf._m().append_audit("admin.retention", p["name"], {"days": item.days, "deleted": counts})
    return {"days": item.days, "deleted": counts, "note": "The audit log is never purged."}


@router.get("/api/admin/export")
def export(request: Request) -> JSONResponse:
    p = pf.need_admin(request)
    def rows(con, q: str) -> list[dict[str, Any]]:
        return [dict(r) for r in con.execute(q)]
    with pf.db() as con:
        bundle = {"exported_at": pf._m().now(), "version": pf.VERSION,
                  "bots": rows(con, "SELECT id,name,role,system,color,model,scopes,spaces,template,icon,team,status,criticality,source,trust,source_ref,owner,created_at FROM bots"),
                  "teams": rows(con, "SELECT * FROM teams"), "notes": rows(con, "SELECT * FROM notes"), "note_versions": rows(con, "SELECT * FROM note_versions"),
                  "grants": rows(con, "SELECT * FROM grants"), "calls": rows(con, "SELECT * FROM calls"), "research": rows(con, "SELECT * FROM research"),
                  "connected_apps": rows(con, "SELECT * FROM apps"), "mcp_servers": rows(con, "SELECT id,name,url,tools,created_by,created_at FROM mcp_servers")}
    pf._m().append_audit("admin.export", p["name"], {"notes": len(bundle["notes"]), "bots": len(bundle["bots"])})
    return JSONResponse(bundle, headers={"Content-Disposition": "attachment; filename=cfa-export.json"})
