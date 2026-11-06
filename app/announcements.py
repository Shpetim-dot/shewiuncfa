"""Announcements for engineering teams.

A small, honest notice board: platform-wide messages from the operator plus
organisation-specific notes (incidents, maintenance, deprecations, new features).

Rules:
* Read: any authenticated member sees platform announcements (org_id IS NULL) and the ones
  of their own organisation; expired entries are hidden.
* Write: an admin writes for their own organisation only; platform-wide announcements need a
  super admin, so no customer can broadcast to everyone.
* No HTML is stored or rendered: the body is plain text of bounded length.

Endpoints:
    GET    /api/announcements?audience=engineering&limit=20
    POST   /api/announcements          {title, body, level, audience, expires_in_days, platform?}
    DELETE /api/announcements/{id}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()
LEVELS = ("info", "warning", "critical", "release")
AUDIENCES = ("engineering", "all")


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=3, max_length=2000)
    level: str = Field(default="info", pattern="^(info|warning|critical|release)$")
    audience: str = Field(default="engineering", pattern="^(engineering|all)$")
    expires_in_days: int = Field(default=30, ge=0, le=365)
    platform: bool = False  # super admin only


def _out(r) -> dict[str, Any]:
    return {"id": r["id"], "title": r["title"], "body": r["body"], "level": r["level"],
            "audience": r["audience"], "platform": r["org_id"] is None,
            "published_at": r["published_at"], "expires_at": r["expires_at"], "created_by": r["created_by"]}


@router.get("/api/announcements")
def list_announcements(request: Request, audience: str = "", limit: int = 20) -> dict[str, Any]:
    p = pf._principal(request)
    if not p.get("org_id") and not p.get("open"):
        return {"announcements": []}  # anonymous visitors have no notice board
    limit = max(1, min(limit, 50))
    now = pf._m().now()
    with pf.db() as con:
        if p.get("org_id"):
            rows = con.execute(
                "SELECT * FROM announcements WHERE (org_id IS NULL OR org_id=?) "
                "AND (expires_at IS NULL OR expires_at > ?) ORDER BY published_at DESC LIMIT ?",
                (p["org_id"], now, limit)).fetchall()
        else:  # open dev mode / operator without an organisation
            rows = con.execute(
                "SELECT * FROM announcements WHERE org_id IS NULL AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY published_at DESC LIMIT ?", (now, limit)).fetchall()
    out = [_out(r) for r in rows if not audience or r["audience"] == audience or r["audience"] == "all"]
    return {"announcements": out}


@router.post("/api/announcements", status_code=201)
def create_announcement(item: AnnouncementIn, request: Request) -> dict[str, Any]:
    principal = pf.need_admin(request)
    from app import auth
    platform = bool(item.platform)
    if platform and auth.rank(principal.get("role")) < auth.rank("super_admin"):
        raise HTTPException(403, "platform announcements need a super admin")
    org_id = None if platform else pf.org()
    if not platform and not org_id:
        org_id = pf.DEFAULT_ORG
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(days=item.expires_in_days)).isoformat() if item.expires_in_days else None
    aid = str(uuid4())
    with pf.db() as con:
        con.execute("INSERT INTO announcements (id,org_id,title,body,level,audience,published_at,expires_at,created_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (aid, org_id, item.title.strip(), item.body.strip(), item.level, item.audience,
                     now.isoformat(), expires, principal["name"]))
        row = con.execute("SELECT * FROM announcements WHERE id=?", (aid,)).fetchone()
    pf._m().append_audit("announcement.created", principal["name"],
                         {"id": aid, "level": item.level, "platform": platform})
    return _out(row)


@router.delete("/api/announcements/{announcement_id}")
def delete_announcement(announcement_id: str, request: Request) -> dict[str, bool]:
    principal = pf.need_admin(request)
    from app import auth
    with pf.db() as con:
        row = con.execute("SELECT * FROM announcements WHERE id=?", (announcement_id,)).fetchone()
        if not row:
            raise HTTPException(404, "announcement not found")
        if row["org_id"] is not None and row["org_id"] != pf.org():
            raise HTTPException(404, "announcement not found")
        if row["org_id"] is None and auth.rank(principal.get("role")) < auth.rank("super_admin"):
            raise HTTPException(403, "platform announcements need a super admin")
        con.execute("DELETE FROM announcements WHERE id=?", (announcement_id,))
    return {"ok": True}


def install(app) -> None:
    app.include_router(router)
