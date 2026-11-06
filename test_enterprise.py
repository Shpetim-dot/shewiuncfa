import json
import sqlite3

import httpx
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app import governance, main, mcp_apps, research


def client(tmp_path, monkeypatch, keys=""):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "e.db")
    for k in ("CFA_MODEL_API_KEY", "CFA_SEARCH_API_KEY", "CFA_ENV"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CFA_API_KEYS", keys)
    monkeypatch.setenv("CFA_DEMO_DELAY", "0")
    main.init_db()
    return TestClient(main.app)


def fake_mcp(seen):
    f = FastAPI()

    @f.post("/mcp")
    async def mcp(req: Request):
        b = await req.json()
        m, i = b.get("method"), b.get("id")
        seen.append(req.headers.get("authorization"))
        if m == "notifications/initialized":
            return Response(status_code=202)
        if m == "initialize":
            res = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}
        elif m == "tools/list":
            res = {"tools": [{"name": "get_weather", "description": "Weather", "annotations": {"readOnlyHint": True}}, {"name": "send_email", "description": "Send"}, {"name": "read_api_key"}]}
        elif m == "tools/call":
            res = {"content": [{"type": "text", "text": "called " + b["params"]["name"] + " " + json.dumps(b["params"]["arguments"])}]}
        else:
            return {"jsonrpc": "2.0", "id": i, "error": {"code": -32601, "message": "nope"}}
        return {"jsonrpc": "2.0", "id": i, "result": res}
    return f


def test_streamed_call_emits_live_events_and_security_headers(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    with c.stream("POST", "/api/calls/stream", json={"topic": "Pilot supplier payments", "bot_ids": ["strategist", "skeptic", "builder"], "rounds": 1}) as r:
        evs = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
        assert r.headers["x-content-type-options"] == "nosniff"
    types = [e["type"] for e in evs]
    assert types[0] == "start" and types.count("turn") == 6 and types.count("round") == 2 and types[-2:] == ["decision", "done"]
    assert any(e["type"] == "activity" and "memory drafts" in e["text"] for e in evs)


def test_production_fails_closed_and_health_warns(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    h = c.get("/api/health")
    assert "frame-ancestors 'none'" in h.headers["content-security-policy"]
    assert any("Authentication is disabled" in w for w in h.json()["warnings"])
    monkeypatch.setenv("CFA_ENV", "production")
    assert c.get("/api/bots").status_code == 503 and c.get("/api/health").status_code == 200


def test_suspend_blocks_everything_and_resume_restores(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    assert c.post("/api/bots/builder/status", json={"status": "suspended", "reason": "test"}).status_code == 200
    assert c.post("/api/bots/builder/messages", json={"content": "hi"}).status_code == 423
    assert c.post("/api/calls", json={"topic": "Some topic here", "bot_ids": ["strategist", "builder"]}).status_code == 403
    assert c.post("/api/bots/builder/tools", json={"app": "datadog", "tool": "list_monitors"}).status_code == 403
    assert {i["id"]: i for i in c.get("/api/inventory").json()}["builder"]["risk"]["level"] == "suspended"
    c.post("/api/bots/builder/status", json={"status": "active"})
    assert c.post("/api/bots/builder/messages", json={"content": "hi"}).status_code == 200
    types = [e["event_type"] for e in c.get("/api/security/audit?limit=80").json()["events"]]
    assert "agent.suspended" in types and "agent.resumed" in types


def test_team_shares_a_private_space_and_leaving_removes_it(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    ids = [c.post("/api/bots", json={"template": "research-analyst", "name": n}).json()["id"] for n in ("Alpha", "Beta", "Gamma")]
    t = c.post("/api/teams", json={"name": "Alpha Team", "mission": "x", "members": ids[:2]}).json()
    assert t["space"] == "team:alpha-team" and {m["id"] for m in t["members"]} == set(ids[:2])
    assert c.post("/api/teams", json={"name": "Alpha Team"}).status_code == 409
    c.post("/api/brain/notes", json={"title": "Team plan", "body": "alphaplan details here", "space": "team:alpha-team"})
    from app.cfa_core import db, retrieve
    spaces = {b["id"]: b["spaces"] for b in c.get("/api/bots").json()}
    assert spaces[ids[0]] == ["shared", "team:alpha-team", "agent:alpha"]
    with db() as con:
        assert retrieve(con, "alphaplan details", spaces=tuple(spaces[ids[0]]))
        assert not retrieve(con, "alphaplan details", spaces=tuple(spaces[ids[2]]))
    c.put(f"/api/teams/{t['id']}", json={"name": "Alpha Team", "mission": "x", "members": [ids[0]]})
    assert "team:alpha-team" not in {b["id"]: b["spaces"] for b in c.get("/api/bots").json()}[ids[1]]
    assert c.delete(f"/api/teams/{t['id']}").status_code == 200


def test_marketplace_import_quarantines_unverified_sources(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    hf = FastAPI()

    @hf.get("/api/models")
    async def models(search: str = ""):
        return [{"id": "acme/tiny-llm", "downloads": 1200, "likes": 5, "pipeline_tag": "text-generation", "tags": ["a"]}, {"id": "bad id", "downloads": 1}]

    @hf.get("/api/models/{owner}/{name}")
    async def model(owner: str, name: str):
        return {"id": f"{owner}/{name}"} if f"{owner}/{name}" == "acme/tiny-llm" else Response(status_code=404)
    monkeypatch.setattr(governance, "HF_TRANSPORT", httpx.ASGITransport(app=hf))
    cards = c.get("/api/marketplace/huggingface?q=tiny").json()
    assert [x["id"] for x in cards] == ["acme/tiny-llm"]
    b = c.post("/api/marketplace/import", json={"source": "huggingface", "ref": "acme/tiny-llm", "name": "Tiny"}).json()
    assert b["scopes"] == ["memory.read", "call.join"] and b["trust"] == "unverified"
    inv = {i["id"]: i for i in c.get("/api/inventory").json()}[b["id"]]
    assert inv["source"] == "huggingface" and inv["trust"] == "unverified" and inv["source_ref"] == "acme/tiny-llm"
    assert c.post("/api/marketplace/import", json={"source": "huggingface", "ref": "acme/missing", "name": "Nope"}).status_code == 422
    assert c.post("/api/marketplace/import", json={"source": "huggingface", "ref": "not a model", "name": "Nope"}).status_code == 422
    soc = c.post("/api/marketplace/import", json={"source": "curated", "ref": "soc-triage", "name": "SOC One"}).json()
    assert soc["scopes"] == ["memory.read", "call.join"]
    card = c.get("/api/bots/skeptic/card").json()
    assert "memory" not in json.dumps(card).replace("memory.", "")
    got = c.post("/api/marketplace/import", json={"source": "card", "name": "Copy", "card": {**card, "suggested_scopes": ["payments.propose"]}}).json()
    assert got["scopes"] == ["memory.read", "call.join"] and got["trust"] == "unverified"
    assert c.post("/api/marketplace/import", json={"source": "card", "name": "Bad", "card": {"system": "x"}}).status_code == 422
    selftest = c.post("/api/selftest").json()
    assert selftest["failed"] == 0 and any("Unverified-source agents" in p["name"] for p in selftest["probes"])


def test_live_mcp_server_end_to_end(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    seen: list = []
    monkeypatch.setattr(mcp_apps, "TRANSPORT", httpx.ASGITransport(app=fake_mcp(seen)))
    monkeypatch.setenv("CFA_MCP_ALLOW_PRIVATE", "1")
    monkeypatch.setenv("CFA_SECRET_KEY", Fernet.generate_key().decode())
    r = c.post("/api/mcp/servers", json={"name": "Weather Hub", "url": "http://mcp.test/mcp", "token": "s3cr3t-token"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert {t["name"]: t["risk"] for t in r.json()["tools"]} == {"get_weather": "read", "send_email": "write", "read_api_key": "secret"}
    assert "s3cr3t-token" not in r.text + c.get("/api/apps").text
    stored = sqlite3.connect(main.DB_PATH).execute("SELECT token_enc FROM mcp_servers").fetchone()[0]
    assert "s3cr3t-token" not in stored and "Bearer s3cr3t-token" in seen
    assert c.put(f"/api/bots/builder/apps/{sid}", json={"tools": ["read_api_key"]}).status_code == 422
    assert c.put(f"/api/bots/builder/apps/{sid}", json={"tools": ["get_weather", "send_email"]}).status_code == 200
    read = c.post("/api/bots/builder/tools", json={"app": sid, "tool": "get_weather", "args": {"city": "Zurich"}}).json()
    assert read["status"] == "completed" and read["live"] and "called get_weather" in read["result"]
    w = c.post("/api/bots/builder/tools", json={"app": sid, "tool": "send_email", "args": {"to": "a@b.c"}}).json()
    assert w["status"] == "pending_approval"
    aid = w["approval"]["id"]
    assert "a@b.c" in w["approval"]["description"]
    assert c.post(f"/api/tool-calls/{aid}/execute").status_code == 409
    assert c.post(f"/api/security/approvals/{aid}/decision", json={"decision": "approved", "decided_by": "x"}).status_code == 200
    ex = c.post(f"/api/tool-calls/{aid}/execute").json()
    assert ex["status"] == "executed" and "called send_email" in ex["result"]
    assert c.post(f"/api/tool-calls/{aid}/execute").status_code == 409
    assert c.post("/api/bots/skeptic/tools", json={"app": sid, "tool": "get_weather"}).status_code == 403
    assert c.post("/api/selftest").json()["failed"] == 0
    assert c.delete(f"/api/mcp/servers/{sid}").status_code == 200


def test_mcp_ssrf_and_token_storage_guards(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.delenv("CFA_MCP_ALLOW_PRIVATE", raising=False)
    monkeypatch.delenv("CFA_SECRET_KEY", raising=False)
    assert c.post("/api/mcp/servers", json={"name": "Local", "url": "https://localhost/mcp"}).status_code == 422
    assert c.post("/api/mcp/servers", json={"name": "Meta", "url": "https://169.254.169.254/latest"}).status_code == 422
    assert c.post("/api/mcp/servers", json={"name": "Plain", "url": "http://example.org/mcp"}).status_code == 422
    assert c.post("/api/mcp/servers", json={"name": "Tok", "url": "https://example.org/mcp", "token": "abc"}).status_code == 400


def test_deep_research_cites_brain_and_web_sources(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    r = c.post("/api/research", json={"question": "How should payment approvals and spend caps work for AI agents?", "depth": "standard"}).json()
    assert r["mode"] == "demo" and len(r["sources"]) >= 3 and "[1]" in r["markdown"]
    assert len(r["chart"]["labels"]) == len(r["chart"]["values"]) > 0 and not any(s["kind"] == "web" for s in r["sources"])
    assert c.post(f"/api/research/{r['id']}/save").json()["status"] == "draft"
    brave = FastAPI()

    @brave.get("/res/v1/web/search")
    async def search(q: str = ""):
        return {"web": {"results": [{"title": "<b>Spend</b> caps", "url": "https://example.org/a", "description": "Caps limit <i>risk</i>."}, {"title": "bad", "url": "javascript:alert(1)", "description": "x"}]}}
    monkeypatch.setattr(research, "SEARCH_TRANSPORT", httpx.ASGITransport(app=brave))
    monkeypatch.setenv("CFA_SEARCH_API_KEY", "k")
    w = c.post("/api/research", json={"question": "What do spend caps do for payment risk?", "depth": "quick", "web": True}).json()
    web = [s for s in w["sources"] if s["kind"] == "web"]
    assert web and all(s["ref"].startswith("https://") and "<" not in s["title"] for s in web)


def test_audit_export_and_brain_activity(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A,mem:member:B")
    h = lambda t: {"Authorization": f"Bearer {t}"}
    c.post("/api/brain/notes", json={"title": "Spend cap rule", "body": "payments limit rule text"}, headers=h("adm"))
    c.post("/api/bots/strategist/messages", json={"content": "payments limit rule"}, headers=h("mem"))
    assert c.get("/api/security/audit/export", headers=h("mem")).status_code == 403
    lines = [json.loads(x) for x in c.get("/api/security/audit/export", headers=h("adm")).text.splitlines()]
    assert lines and all("event_hash" in x for x in lines)
    ev = c.get("/api/brain/activity", headers=h("mem")).json()["events"]
    assert {(e["kind"], e["bot_id"]) for e in ev} >= {("read", "strategist"), ("write", "strategist")}
    assert c.get("/api/brain/activity?since=9999", headers=h("mem")).json()["events"] == []
