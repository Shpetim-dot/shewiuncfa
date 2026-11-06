"""MCP apps: a demo catalog plus LIVE MCP servers (Streamable HTTP) with per-agent tool grants.

Governance: an admin connects an app, each agent needs an explicit grant per tool, read tools run
immediately, write tools only create an approval request (executed after a human approves),
secret-looking tools can never be granted. Tokens are encrypted at rest and never returned.
Supported: MCP over Streamable HTTP with optional bearer token. Not supported: OAuth, legacy SSE-only servers.
"""
from __future__ import annotations

import ipaddress
import hashlib
import json
from datetime import datetime, timedelta, timezone
import os
import re
import socket
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from app import cfa_core as pf

router = APIRouter()


def _act(bot_id: str, kind: str, text: str) -> None:
    with pf.db() as con:
        pf.log_act(con, bot_id, kind, text)


TRANSPORT: httpx.AsyncBaseTransport | None = None  # tests inject an in-process MCP server
SECRET_NAME = re.compile(r"(secret|password|passwd|token|credential|private[_-]?key|api[_-]?key)", re.I)
APPS: dict[str, dict[str, Any]] = {
    "datadog": {"name": "Datadog", "category": "Observability", "description": "Inspect metrics and monitors", "tools": [("query_metrics", "read"), ("list_monitors", "read"), ("mute_monitor", "write")]},
    "sentry": {"name": "Sentry", "category": "Observability", "description": "Errors and releases", "tools": [("list_issues", "read"), ("resolve_issue", "write")]},
    "cloudflare": {"name": "Cloudflare", "category": "Infrastructure", "description": "Zones, DNS and cache", "tools": [("list_zones", "read"), ("purge_cache", "write")]},
    "firebase": {"name": "Firebase", "category": "Infrastructure", "description": "Projects and app configuration", "tools": [("list_projects", "read"), ("update_remote_config", "write")]},
    "azure": {"name": "Azure", "category": "Infrastructure", "description": "Resources and deployments", "tools": [("list_resources", "read"), ("restart_service", "write")]},
    "redis": {"name": "Redis", "category": "Data", "description": "Keys and streams", "tools": [("get_key", "read"), ("delete_key", "write")]},
    "notion": {"name": "Notion", "category": "Productivity", "description": "Pages and databases", "tools": [("search_pages", "read"), ("create_page", "write")]},
    "atlassian": {"name": "Atlassian", "category": "Productivity", "description": "Jira issues and Confluence pages", "tools": [("search_issues", "read"), ("create_issue", "write")]},
    "1password": {"name": "1Password", "category": "Secrets", "description": "Vault items", "tools": [("list_vault_items", "read"), ("read_secret", "secret")]},
}


# ---------- safety helpers ----------
def check_url(url: str) -> None:
    u = urlparse(url)
    relaxed = os.getenv("CFA_MCP_ALLOW_PRIVATE") == "1"
    if u.scheme not in ("https", "http") or not u.hostname:
        raise HTTPException(422, "MCP URL must start with https://")
    if u.scheme == "http" and not relaxed and os.getenv("CFA_MCP_ALLOW_INSECURE") != "1":
        raise HTTPException(422, "use https for MCP servers")
    if relaxed:
        return
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    except OSError:
        raise HTTPException(422, "host cannot be resolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise HTTPException(422, "private or internal addresses are not allowed")


def _fernet():
    key = os.getenv("CFA_SECRET_KEY")
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet
        return Fernet(key.encode())
    except Exception:
        raise HTTPException(500, "CFA_SECRET_KEY is invalid")


def _token(row) -> str | None:
    if not row["token_enc"]:
        return None
    f = _fernet()
    if not f:
        raise HTTPException(500, "CFA_SECRET_KEY is required to use stored tokens")
    return f.decrypt(row["token_enc"].encode()).decode()


# ---------- approval binding ----------
def payload_hash(bot_id: str, app_id: str, tool: str, args: Any) -> str:
    """Hash of the exact action: who, where, which tool, which arguments. An approval is only valid for this hash."""
    return hashlib.sha256(json.dumps({"bot": bot_id, "app": app_id, "tool": tool, "args": args}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def policy_version(con, bot_id: str, app_id: str, tool: str, risk: str | None) -> str:
    """Changes when the permission picture for this action changes (grant set on the app, or the tool's risk class)."""
    granted = sorted(r["tool"] for r in con.execute("SELECT tool FROM grants WHERE bot_id=? AND app_id=?", (bot_id, app_id)))
    return hashlib.sha256(json.dumps({"granted": granted, "tool": tool, "risk": risk}, sort_keys=True).encode()).hexdigest()[:16]


def approval_ttl_minutes() -> int:
    try:
        return max(1, int(os.getenv("CFA_APPROVAL_TTL_MINUTES", "1440")))
    except ValueError:
        return 1440


# ---------- MCP client (Streamable HTTP, JSON-RPC) ----------
def _result(r: httpx.Response, rid: int) -> dict[str, Any]:
    if r.status_code >= 400:
        raise HTTPException(502, f"MCP server returned HTTP {r.status_code}")
    if len(r.content) > 1_000_000:
        raise HTTPException(502, "MCP response too large")
    msg: dict[str, Any] | None = None
    if "text/event-stream" in r.headers.get("content-type", ""):
        for line in r.text.splitlines():
            if line.startswith("data:"):
                try:
                    cand = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if isinstance(cand, dict) and cand.get("id") == rid:
                    msg = cand
    else:
        try:
            msg = r.json()
        except ValueError:
            msg = None
    if not isinstance(msg, dict):
        raise HTTPException(502, "MCP server sent an unreadable response")
    if "error" in msg:
        raise HTTPException(502, "MCP error: " + str((msg["error"] or {}).get("message", "unknown"))[:200])
    return msg.get("result") or {}


async def rpc(url: str, token: str | None, method: str, params: dict[str, Any]) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(transport=TRANSPORT, timeout=15, follow_redirects=False) as c:
            r = await c.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "shewiun-cfa", "version": "0.3"}}})
            _result(r, 1)
            if r.headers.get("mcp-session-id"):
                headers["Mcp-Session-Id"] = r.headers["mcp-session-id"]
            await c.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
            return _result(await c.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params}), 2)
    except httpx.HTTPError:
        raise HTTPException(502, "Could not reach the MCP server")


async def discover(url: str, token: str | None) -> list[dict[str, str]]:
    res = await rpc(url, token, "tools/list", {})
    out = []
    for t in (res.get("tools") or [])[:50]:
        name = str(t.get("name", ""))
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}", name):
            continue
        risk = "secret" if SECRET_NAME.search(name) else ("read" if (t.get("annotations") or {}).get("readOnlyHint") is True else "write")
        out.append({"name": name, "risk": risk, "description": str(t.get("description", ""))[:160]})
    return out


async def live_call(app: dict[str, Any], tool: str, args: dict[str, Any]) -> str:
    res = await rpc(app["url"], app["token"], "tools/call", {"name": tool, "arguments": args})
    text = "\n".join(str(c.get("text", "")) for c in (res.get("content") or []) if isinstance(c, dict) and c.get("type") == "text")[:4000]
    return ("Tool reported an error: " + text) if res.get("isError") else text


# ---------- registry ----------
def resolve(con, app_id: str) -> dict[str, Any] | None:
    if app_id in APPS:
        a = APPS[app_id]
        return {"id": app_id, "name": a["name"], "live": False, "tools": list(a["tools"])}
    r = con.execute("SELECT * FROM mcp_servers WHERE id=?", (app_id,)).fetchone()
    if not r:
        return None
    return {"id": app_id, "name": r["name"], "live": True, "tools": [(t["name"], t["risk"]) for t in json.loads(r["tools"])], "url": r["url"], "token": _token(r)}


def connected_apps(con) -> dict[str, list[tuple[str, str]]]:
    out = {r["id"]: list(APPS[r["id"]]["tools"]) for r in con.execute("SELECT id FROM apps") if r["id"] in APPS}
    for r in con.execute("SELECT id,tools FROM mcp_servers"):
        out[r["id"]] = [(t["name"], t["risk"]) for t in json.loads(r["tools"])]
    return out


def risk_map(con) -> dict[tuple[str, str], str]:
    return {(a, t): rk for a, tools in connected_apps(con).items() for t, rk in tools}


LOGO = {"datadog": "datadog", "sentry": "sentry", "cloudflare": "cloudflare", "firebase": "firebase", "azure": "microsoftazure", "redis": "redis", "notion": "notion", "atlassian": "atlassian", "1password": "1password"}


def connect(con, app_id: str, actor: str) -> None:
    con.execute("INSERT OR IGNORE INTO apps VALUES (?,?,?)", (app_id, actor, pf._m().now()))


@router.get("/api/apps")
def list_apps() -> list[dict[str, Any]]:
    with pf.db() as con:
        connected = {r["id"] for r in con.execute("SELECT id FROM apps")}
        grants: dict[str, dict[str, list[str]]] = {}
        for r in con.execute("SELECT bot_id,app_id,tool FROM grants"):
            grants.setdefault(r["app_id"], {}).setdefault(r["bot_id"], []).append(r["tool"])
        servers = con.execute("SELECT * FROM mcp_servers").fetchall()
    out = [{"id": k, "name": v["name"], "category": v["category"], "description": v["description"], "connected": k in connected, "live": False,
            "tools": [{"name": t, "risk": r} for t, r in v["tools"]], "grants": grants.get(k, {}), "logo": LOGO.get(k)} for k, v in APPS.items()]
    for s in servers:
        out.insert(0, {"id": s["id"], "name": s["name"], "category": "Live MCP server", "description": "Live server at " + urlparse(s["url"]).netloc, "connected": True, "live": True,
                       "tools": [{"name": t["name"], "risk": t["risk"], "description": t.get("description", "")} for t in json.loads(s["tools"])], "grants": grants.get(s["id"], {})})
    return out


@router.post("/api/apps/{app_id}/{action}")
def toggle(app_id: str, action: str, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    if app_id not in APPS or action not in ("connect", "disconnect"):
        raise HTTPException(404, "unknown app or action")
    with pf.db() as con:
        if action == "connect":
            connect(con, app_id, p["name"])
        else:
            con.execute("DELETE FROM apps WHERE id=?", (app_id,))
            con.execute("DELETE FROM grants WHERE app_id=?", (app_id,))
    pf._m().append_audit(f"app.{action}ed", p["name"], {"app": app_id, "mode": "demo"})
    return {"id": app_id, "connected": action == "connect", "mode": "demo"}


class ServerIn(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    url: str = Field(max_length=300)
    token: str | None = Field(default=None, max_length=500)


def _server_out(sid: str, name: str, tools: list[dict[str, str]]) -> dict[str, Any]:
    return {"id": sid, "name": name, "live": True, "tools": tools}


@router.post("/api/mcp/servers", status_code=201)
async def add_server(item: ServerIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    enc = None
    if item.token:
        f = _fernet()
        if not f:
            raise HTTPException(400, "Set CFA_SECRET_KEY to store tokens (it encrypts them at rest)")
        enc = f.encrypt(item.token.encode()).decode()
    check_url(item.url)
    from app import billing
    with pf.db() as con:
        billing.check_count("mcp_servers", con.execute("SELECT COUNT(*) FROM mcp_servers").fetchone()[0])
    tools = await discover(item.url, item.token)
    if not tools:
        raise HTTPException(422, "The server exposes no usable tools")
    slug = re.sub(r"[^a-z0-9]+", "-", item.name.lower()).strip("-")[:24] or "server"
    with pf.db() as con:
        sid = f"mcp-{slug}"
        if con.execute("SELECT 1 FROM mcp_servers WHERE id=?", (sid,)).fetchone():
            sid = f"{sid}-{uuid4().hex[:4]}"
        con.execute("INSERT INTO mcp_servers VALUES (?,?,?,?,?,?,?)", (sid, item.name.strip(), item.url, enc, json.dumps(tools), p["name"], pf._m().now()))
    pf._m().append_audit("mcp.server.added", p["name"], {"id": sid, "host": urlparse(item.url).netloc, "tools": len(tools)})
    return _server_out(sid, item.name.strip(), tools)


@router.post("/api/mcp/servers/{sid}/refresh")
async def refresh_server(sid: str, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    with pf.db() as con:
        app = resolve(con, sid)
    if not app or not app["live"]:
        raise HTTPException(404, "server not found")
    tools = await discover(app["url"], app["token"])
    with pf.db() as con:
        con.execute("UPDATE mcp_servers SET tools=? WHERE id=?", (json.dumps(tools), sid))
        con.execute("DELETE FROM grants WHERE app_id=? AND tool NOT IN (%s)" % ",".join("?" * len(tools)) if tools else "DELETE FROM grants WHERE app_id=?", (sid, *[t["name"] for t in tools]) if tools else (sid,))
    pf._m().append_audit("mcp.server.refreshed", p["name"], {"id": sid, "tools": len(tools)})
    return _server_out(sid, app["name"], tools)


@router.delete("/api/mcp/servers/{sid}")
def delete_server(sid: str, request: Request) -> dict[str, str]:
    p = pf.need_admin(request)
    with pf.db() as con:
        if not con.execute("SELECT 1 FROM mcp_servers WHERE id=?", (sid,)).fetchone():
            raise HTTPException(404, "server not found")
        con.execute("DELETE FROM mcp_servers WHERE id=?", (sid,))
        con.execute("DELETE FROM grants WHERE app_id=?", (sid,))
    pf._m().append_audit("mcp.server.removed", p["name"], {"id": sid})
    return {"status": "removed"}


class GrantIn(BaseModel):
    tools: list[str] = Field(max_length=60)


@router.put("/api/bots/{bot_id}/apps/{app_id}")
def set_grants(bot_id: str, app_id: str, item: GrantIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    with pf.db() as con:
        app = resolve(con, app_id)
        if not app:
            raise HTTPException(404, "unknown app")
        risks = dict(app["tools"])
        if any(t not in risks for t in item.tools):
            raise HTTPException(422, "unknown tool")
        if any(risks[t] == "secret" for t in item.tools):
            raise HTTPException(422, "secret tools cannot be granted (policy: secrets.read is denied)")
        if not con.execute("SELECT 1 FROM bots WHERE id=?", (bot_id,)).fetchone():
            raise HTTPException(404, "agent not found")
        if not app["live"] and not con.execute("SELECT 1 FROM apps WHERE id=?", (app_id,)).fetchone():
            raise HTTPException(409, "app is not connected")
        before = [r["tool"] for r in con.execute("SELECT tool FROM grants WHERE bot_id=? AND app_id=?", (bot_id, app_id))]
        con.execute("DELETE FROM grants WHERE bot_id=? AND app_id=?", (bot_id, app_id))
        con.executemany("INSERT INTO grants VALUES (?,?,?)", [(bot_id, app_id, t) for t in item.tools])
    pf._m().append_audit("agent.grants.changed", p["name"], {"agent": bot_id, "app": app_id, "before": before, "after": item.tools})
    return {"agent": bot_id, "app": app_id, "tools": item.tools}


class ToolIn(BaseModel):
    app: str = Field(max_length=60)
    tool: str = Field(max_length=64)
    dry_run: bool = False
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("args")
    @classmethod
    def small(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(v)) > 4000:
            raise ValueError("args too large")
        return v


@router.post("/api/bots/{bot_id}/tools")
async def call_tool(bot_id: str, item: ToolIn, request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    m = pf._m()
    with pf.db() as con:
        app = resolve(con, item.app)
        risk = dict(app["tools"]).get(item.tool) if app else None
        if not risk:
            raise HTTPException(404, "unknown app or tool")
        bot = con.execute("SELECT name,status FROM bots WHERE id=?", (bot_id,)).fetchone()
        if not bot:
            raise HTTPException(404, "agent not found")
        connected = app["live"] or con.execute("SELECT 1 FROM apps WHERE id=?", (item.app,)).fetchone()
        granted = con.execute("SELECT 1 FROM grants WHERE bot_id=? AND app_id=? AND tool=?", (bot_id, item.app, item.tool)).fetchone()
    if not connected:
        raise HTTPException(409, "app is not connected")
    if bot["status"] == "suspended" or not granted or risk == "secret":
        m.append_audit("agent.denied", p["name"], {"agent": bot_id, "app": item.app, "tool": item.tool, "suspended": bot["status"] == "suspended"})
        if not item.dry_run:
            _act(bot_id, "denied", f"blocked: {item.app}.{item.tool}")
        raise HTTPException(403, f"agent has no grant for {item.app}.{item.tool}" if bot["status"] != "suspended" else "agent is suspended")
    if item.dry_run:
        return {"allowed": True, "dry_run": True, "risk": risk, "requires_approval": risk == "write"}
    if risk == "read":
        text = await live_call(app, item.tool, item.args) if app["live"] else f"DEMO: {item.app}.{item.tool} would return sample data. No external service was contacted."
        m.append_audit("tool.call", p["name"], {"agent": bot_id, "app": item.app, "tool": item.tool, "live": app["live"], "arg_keys": sorted(item.args)})
        _act(bot_id, "tool", f"{item.app}.{item.tool} completed")
        return {"status": "completed", "live": app["live"], "demo": not app["live"], "result": text}
    ph = payload_hash(bot_id, item.app, item.tool, item.args)
    exp = (datetime.now(timezone.utc) + timedelta(minutes=approval_ttl_minutes())).isoformat()
    rec = m.request_approval(m.ApprovalIn(action_type="external.write", description=f"[{bot['name']}] {item.app}.{item.tool} payload={ph[:12]} args={json.dumps(item.args)[:300]}", requested_by=bot["name"], risk_level="high"))
    with pf.db() as con:
        con.execute("INSERT INTO pending_calls (approval_id,bot_id,app_id,tool,args,status,result,created_at,payload_hash,expires_at,policy_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (rec["id"], bot_id, item.app, item.tool, json.dumps(item.args), "pending", None, m.now(), ph, exp, policy_version(con, bot_id, item.app, item.tool, risk)))
    m.append_audit("tool.pending", p["name"], {"agent": bot_id, "app": item.app, "tool": item.tool, "approval_id": rec["id"], "live": app["live"]})
    _act(bot_id, "tool", f"{item.app}.{item.tool} is waiting for human approval")
    return {"status": "pending_approval", "approval": rec, "live": app["live"], "demo": not app["live"], "note": "Nothing was executed. Execute it after a human approves."}


@router.get("/api/tool-calls")
def list_tool_calls() -> list[dict[str, Any]]:
    with pf.db() as con:
        rows = con.execute("SELECT p.*, a.status AS approval_status FROM pending_calls p LEFT JOIN approval_requests a ON a.id=p.approval_id ORDER BY p.created_at DESC LIMIT 30").fetchall()
    return [{"approval_id": r["approval_id"], "bot_id": r["bot_id"], "app": r["app_id"], "tool": r["tool"], "args": json.loads(r["args"]), "status": r["status"], "approval_status": r["approval_status"], "result": r["result"],
             "payload_hash": (r["payload_hash"] or "")[:12], "expires_at": r["expires_at"]} for r in rows]


@router.post("/api/tool-calls/{approval_id}/execute")
async def execute(approval_id: str, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    m = pf._m()
    with pf.db() as con:
        pc = con.execute("SELECT * FROM pending_calls WHERE approval_id=?", (approval_id,)).fetchone()
        ap = con.execute("SELECT status FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        app = resolve(con, pc["app_id"]) if pc else None
    if not pc or not ap:
        raise HTTPException(404, "no pending tool call for this approval")
    if pc["status"] != "pending":
        raise HTTPException(409, "this call was already executed")
    if ap["status"] != "approved":
        raise HTTPException(409, "a human must approve the request first")
    if not app:
        raise HTTPException(409, "the app is no longer connected")
    def invalidate(status: str, why: str, code: int = 409):
        with pf.db() as con:
            con.execute("UPDATE pending_calls SET status=?, result=? WHERE approval_id=? AND status='pending'", (status, why, approval_id))
        m.append_audit("tool.invalidated", p["name"], {"approval_id": approval_id, "app": pc["app_id"], "tool": pc["tool"], "reason": why})
        raise HTTPException(code, why)

    # The approval covers exactly one action. If the stored payload no longer matches its hash, the approval is void.
    if not pc["payload_hash"]:
        invalidate("invalidated", "this approval predates payload binding; request the action again")
    if payload_hash(pc["bot_id"], pc["app_id"], pc["tool"], json.loads(pc["args"])) != pc["payload_hash"]:
        invalidate("invalidated", "the action changed after it was approved; the approval is void")
    if pc["expires_at"] and m.now() > pc["expires_at"]:
        invalidate("expired", "the approval expired; request the action again")
    # Revalidate authorization right before the side effect (grant revoked / agent suspended after approval).
    with pf.db() as con:
        bot = con.execute("SELECT status FROM bots WHERE id=?", (pc["bot_id"],)).fetchone()
        granted = con.execute("SELECT 1 FROM grants WHERE bot_id=? AND app_id=? AND tool=?", (pc["bot_id"], pc["app_id"], pc["tool"])).fetchone()
        risk = dict(app["tools"]).get(pc["tool"])
        now_pv = policy_version(con, pc["bot_id"], pc["app_id"], pc["tool"], risk)
    if pc["policy_version"] and bot and now_pv != pc["policy_version"]:
        invalidate("invalidated", "permissions changed after approval; request the action again", 403)
    if not bot or bot["status"] == "suspended" or not granted or not risk or risk == "secret":
        m.append_audit("tool.blocked", p["name"], {"approval_id": approval_id, "app": pc["app_id"], "tool": pc["tool"], "reason": "authorization changed after approval"})
        raise HTTPException(403, "authorization changed after approval; the action was not executed")
    # Atomic claim: only one concurrent request may move pending -> executing (no duplicate side effects).
    with pf.db() as con:
        claimed = con.execute("UPDATE pending_calls SET status='executing' WHERE approval_id=? AND status='pending'", (approval_id,)).rowcount
    if claimed != 1:
        raise HTTPException(409, "this call was already executed or is executing")
    try:
        text = await live_call(app, pc["tool"], json.loads(pc["args"])) if app["live"] else f"DEMO: {pc['app_id']}.{pc['tool']} would run now. No external service was contacted."
        status = "executed"
    except HTTPException as e:
        text, status = str(e.detail), "failed"
    with pf.db() as con:
        con.execute("UPDATE pending_calls SET status=?, result=? WHERE approval_id=?", (status, text, approval_id))
    m.append_audit("tool." + status, p["name"], {"approval_id": approval_id, "app": pc["app_id"], "tool": pc["tool"], "live": app["live"]})
    _act(pc["bot_id"], "tool", f"{pc['app_id']}.{pc['tool']} {status} after approval")
    return {"status": status, "result": text, "live": app["live"]}
