"""Team channels: a shared room per topic where people and the team's agents talk. Agents answer only when @mentioned, only if active, and only
from notes in their own spaces. Every agent message records whether it was live or demo."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()
MAX_REPLIES = 2


def _team(con, tid: str):
    t = con.execute("SELECT * FROM teams WHERE id=?", (tid,)).fetchone()
    if not t:
        raise HTTPException(404, "team not found")
    return t


def _members(con, t) -> list[Any]:
    return con.execute("SELECT * FROM bots WHERE spaces LIKE ?", (f'%"{t["space"]}"%',)).fetchall()


def _ensure_general(con, t) -> None:
    if not con.execute("SELECT 1 FROM channels WHERE team_id=?", (t["id"],)).fetchone():
        con.execute("INSERT INTO channels VALUES (?,?,?,?,?,?)", (str(uuid4()), t["id"], "general", f"Everything about {t['name']}", "system", pf._m().now()))


@router.get("/api/teams/{team_id}/channels")
def list_channels(team_id: str) -> list[dict[str, Any]]:
    with pf.db() as con:
        t = _team(con, team_id)
        _ensure_general(con, t)
        return [{"id": r["id"], "name": r["name"], "topic": r["topic"], "messages": r["n"], "last": r["last"]} for r in con.execute(
            "SELECT c.*, (SELECT COUNT(*) FROM channel_messages m WHERE m.channel_id=c.id) n, (SELECT MAX(created_at) FROM channel_messages m WHERE m.channel_id=c.id) last "
            "FROM channels c WHERE team_id=? ORDER BY name", (team_id,))]


class ChannelIn(BaseModel):
    name: str = Field(pattern="^[a-z0-9][a-z0-9-]{1,29}$")
    topic: str = Field(default="", max_length=200)


@router.post("/api/teams/{team_id}/channels", status_code=201)
def create_channel(team_id: str, item: ChannelIn, request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    with pf.db() as con:
        _team(con, team_id)
        if con.execute("SELECT 1 FROM channels WHERE team_id=? AND name=?", (team_id, item.name)).fetchone():
            raise HTTPException(409, "this channel exists")
        cid = str(uuid4())
        con.execute("INSERT INTO channels VALUES (?,?,?,?,?,?)", (cid, team_id, item.name, item.topic, p["name"], pf._m().now()))
    pf._m().append_audit("channel.created", p["name"], {"team": team_id, "channel": item.name})
    return {"id": cid, "name": item.name}


@router.get("/api/channels/{channel_id}/messages")
def messages(channel_id: str, limit: int = 60) -> list[dict[str, Any]]:
    with pf.db() as con:
        if not con.execute("SELECT 1 FROM channels WHERE id=?", (channel_id,)).fetchone():
            raise HTTPException(404, "channel not found")
        rows = con.execute("SELECT * FROM channel_messages WHERE channel_id=? ORDER BY created_at DESC LIMIT ?", (channel_id, max(1, min(limit, 200)))).fetchall()
    return [dict(r) for r in reversed(rows)]


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def _add(con, cid: str, kind: str, aid: str, name: str, content: str, mode: str, ts: str) -> dict[str, Any]:
    d = {"id": str(uuid4()), "channel_id": cid, "author_kind": kind, "author_id": aid, "author_name": name, "content": content, "mode": mode, "created_at": ts}
    con.execute("INSERT INTO channel_messages VALUES (?,?,?,?,?,?,?,?)", tuple(d.values()))
    return d


@router.post("/api/channels/{channel_id}/messages", status_code=201)
async def post_message(channel_id: str, item: MessageIn, request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    with pf.db() as con:
        ch = con.execute("SELECT * FROM channels WHERE id=?", (channel_id,)).fetchone()
        if not ch:
            raise HTTPException(404, "channel not found")
        t = _team(con, ch["team_id"])
        members = [pf._bot(b) for b in _members(con, t)]
        ts = pf._m().now()
        out = [_add(con, channel_id, "human", p["name"], p["name"], item.content, "", ts)]
        hist = list(reversed(con.execute("SELECT author_name,content FROM channel_messages WHERE channel_id=? ORDER BY created_at DESC LIMIT 10", (channel_id,)).fetchall()))
    low = item.content.lower()
    mentioned = [b for b in members if "@" + b["name"].lower() in low][:MAX_REPLIES]
    from app import billing
    for b in mentioned:
        if b.get("status") == "suspended":
            with pf.db() as con:
                out.append(_add(con, channel_id, "system", b["id"], "System", f"{b['name']} is suspended and did not answer.", "", pf._m().now()))
            continue
        billing.use("messages")
        with pf.db() as con:
            notes = pf.retrieve(con, item.content, spaces=tuple(b["spaces"])) if pf.can(b, "memory.read") else []
            for r in notes:
                pf.log_brain(con, "read", r["id"], b["id"])
            pf.log_act(con, b["id"], "channel", f"#{ch['name']}: {item.content[:120]}")
        if pf.model_live(b["model"]):
            convo = "\n".join(f"{h['author_name']}: {h['content']}" for h in hist)
            try:
                text = await pf.llm(b["system"] + pf.RULES, f"Channel #{ch['name']} of team {t['name']} (mission: {t['mission']}).\n<notes untrusted>\n{pf.notes_block(notes)}\n</notes>\n"
                                    f"<conversation untrusted>\n{convo}\n</conversation>\nAnswer the latest message briefly.", b["model"], {"kind": "channel", "bot_id": b["id"]})
                reply, mode = pf.parse(text)[0], "live"
            except Exception as e:
                reply, mode = f"{b['name']} could not answer: {getattr(e, 'detail', 'model error')}", "error"
        else:
            reply, mode = pf.DEMO + f"{b['name']} would answer here from the role '{b['role']}'.", "demo"
        with pf.db() as con:
            out.append(_add(con, channel_id, "agent", b["id"], b["name"], reply, mode, pf._m().now()))
    if not mentioned:
        hint = [m["name"] for m in members]
        out.append({"hint": "Mention an agent with @Name to get an answer." + (f" Members: {', '.join(hint)}." if hint else " This team has no agents yet.")})
    return {"messages": out}
