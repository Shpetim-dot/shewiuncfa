import json
import sqlite3

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import brain, main, mcp_apps
from app import cfa_core as pf


def client(tmp_path, monkeypatch, keys=""):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "v7.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("CFA_API_KEYS", keys)
    main.init_db()
    return TestClient(main.app)


def llm_transport(monkeypatch, handler):
    monkeypatch.setattr(pf, "LLM_TRANSPORT", httpx.MockTransport(handler))


def ok(tokens_in=100, tokens_out=50):
    return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": tokens_in, "completion_tokens": tokens_out}})


def ask(c, agent="strategist", text="hi"):
    return c.post(f"/api/bots/{agent}/messages", json={"content": text})


# ---------- approvals: bound to the exact payload, expiring, one execution ----------
def pending_call(c):
    c.post("/api/demo/workspace")
    bots = {b["name"]: b["id"] for b in c.get("/api/bots").json()}
    r = c.post(f"/api/bots/{bots['Nova']}/tools", json={"app": "atlassian", "tool": "create_issue", "args": {"title": "A"}}).json()
    aid = r["approval"]["id"]
    return aid, bots


def approve(c, aid):
    return c.post(f"/api/security/approvals/{aid}/decision", json={"decision": "approved", "decided_by": "x"})


def test_changed_payload_voids_the_approval(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    aid, _ = pending_call(c)
    assert approve(c, aid).status_code == 200
    with pf.db() as con:
        con.execute("UPDATE pending_calls SET args=? WHERE approval_id=?", (json.dumps({"title": "SOMETHING ELSE"}), aid))
    r = c.post(f"/api/tool-calls/{aid}/execute")
    assert r.status_code == 409 and "changed after it was approved" in r.json()["detail"]
    assert [t for t in c.get("/api/tool-calls").json() if t["approval_id"] == aid][0]["status"] == "invalidated"
    assert "tool.invalidated" in [e["event_type"] for e in c.get("/api/security/audit?limit=60").json()["events"]]


def test_expired_approval_is_refused(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    aid, _ = pending_call(c)
    approve(c, aid)
    with pf.db() as con:
        con.execute("UPDATE pending_calls SET expires_at='2000-01-01T00:00:00+00:00' WHERE approval_id=?", (aid,))
    r = c.post(f"/api/tool-calls/{aid}/execute")
    assert r.status_code == 409 and "expired" in r.json()["detail"]


def test_permission_change_after_approval_blocks_execution(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    aid, bots = pending_call(c)
    approve(c, aid)
    with pf.db() as con:
        con.execute("DELETE FROM grants WHERE bot_id=?", (bots["Nova"],))
    r = c.post(f"/api/tool-calls/{aid}/execute")
    assert r.status_code in (403, 409)
    assert [t for t in c.get("/api/tool-calls").json() if t["approval_id"] == aid][0]["status"] != "executed"


def test_a_retry_cannot_execute_twice(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    aid, _ = pending_call(c)
    approve(c, aid)
    assert c.post(f"/api/tool-calls/{aid}/execute").status_code == 200
    assert c.post(f"/api/tool-calls/{aid}/execute").status_code == 409


def test_unapproved_call_does_not_execute(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    aid, _ = pending_call(c)
    assert c.post(f"/api/tool-calls/{aid}/execute").status_code in (403, 409)


# ---------- gateway: usage, prices, fallbacks, budget, providers ----------
def test_usage_uses_provider_tokens_and_cost_is_unknown_without_a_price(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k" * 12)
    llm_transport(monkeypatch, lambda req: ok(120, 30))
    assert ask(c).status_code == 200
    u = c.get("/api/usage").json()
    m = u["models"][0]
    assert (m["tokens_in"], m["tokens_out"], m["calls"]) == (120, 30, 1)
    assert m["cost"] is None and m["calls_with_unknown_cost"] == 1 and u["cost_is_partial"] is True
    assert u["by_kind"]["chat"] == 1


def test_cost_comes_from_a_sourced_price_record(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k" * 12)
    model = pf.resolve_model(None)[3]
    llm_transport(monkeypatch, lambda req: ok(1_000_000, 500_000))
    assert c.put("/api/prices", json={"provider": "default", "model": model, "input_per_mtok": 2, "output_per_mtok": 10, "currency": "USD", "source": "test fixture"}).status_code == 201
    assert c.put("/api/prices", json={"provider": "default", "model": model, "input_per_mtok": 2, "output_per_mtok": 10, "source": ""}).status_code == 422  # no source, no price
    ask(c)
    m = c.get("/api/usage").json()["models"][0]
    assert m["cost"] == 7.0 and m["currency"] == "USD" and m["calls_with_unknown_cost"] == 0


def test_budget_cap_stops_further_calls(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k" * 12)
    model = pf.resolve_model(None)[3]
    llm_transport(monkeypatch, lambda req: ok(1_000_000, 0))
    c.put("/api/prices", json={"provider": "default", "model": model, "input_per_mtok": 5, "output_per_mtok": 5, "source": "test fixture"})
    c.put("/api/usage/budget", json={"amount": 1, "currency": "USD"})
    assert ask(c).status_code == 200  # spends 5, over the cap of 1
    r = ask(c)
    assert r.status_code == 402 and "budget" in r.json()["detail"].lower()


def test_fallback_is_used_only_after_provider_failure_and_is_recorded(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k" * 12)
    seen = []

    def handler(req):
        body = json.loads(req.content)
        seen.append(body["model"])
        return httpx.Response(402, json={}) if body["model"] == "primary-model" else ok()

    llm_transport(monkeypatch, handler)
    c.put("/api/fallbacks", json={"models": ["backup-model"]})
    c.put("/api/bots/strategist/model", json={"model": "primary-model"})
    assert ask(c).status_code == 200
    assert seen == ["primary-model", "backup-model"]
    m = {x["model"]: x for x in c.get("/api/usage").json()["models"]}
    assert m["backup-model"]["fallback_calls"] == 1 and m["primary-model"]["errors"] == 1


def test_provider_registry_encrypts_keys_and_routes_models(tmp_path, monkeypatch):
    monkeypatch.setenv("CFA_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(mcp_apps, "check_url", lambda u: None)
    c = client(tmp_path, monkeypatch)
    secret = "sk-test-SECRET-123456"
    assert c.post("/api/providers", json={"id": "mistral", "base_url": "https://api.mistral.example/v1", "api_key": secret}).status_code == 201
    assert secret not in json.dumps(c.get("/api/providers").json())
    with pf.db() as con:
        assert secret not in con.execute("SELECT key_enc FROM providers").fetchone()[0]
    assert secret not in json.dumps(c.get("/api/security/audit?limit=60").json())
    hits = []

    def handler(req):
        hits.append((str(req.url), req.headers["authorization"]))
        return ok()

    llm_transport(monkeypatch, handler)
    t = c.post("/api/providers/mistral/test", json={"model": "large"}).json()
    assert t["status"] == "ok" and hits[0] == ("https://api.mistral.example/v1/chat/completions", f"Bearer {secret}")
    assert c.get("/api/providers").json()[0]["status"] == "ok"
    assert c.post("/api/providers", json={"id": "hf", "base_url": "https://x.example", "api_key": "12345678"}).status_code == 422  # reserved
    assert c.delete("/api/providers/mistral").status_code == 200


def test_provider_changes_need_admin_and_a_secret_key(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A,mem:member:B")
    body = {"id": "other", "base_url": "https://api.other.example/v1", "api_key": "12345678"}
    assert c.post("/api/providers", json=body, headers={"Authorization": "Bearer mem"}).status_code == 403
    monkeypatch.setattr(mcp_apps, "check_url", lambda u: None)
    monkeypatch.delenv("CFA_SECRET_KEY", raising=False)
    assert c.post("/api/providers", json=body, headers={"Authorization": "Bearer adm"}).status_code == 409


def test_provider_urls_must_be_safe(tmp_path, monkeypatch):
    monkeypatch.setenv("CFA_SECRET_KEY", Fernet.generate_key().decode())
    c = client(tmp_path, monkeypatch)
    for url in ("http://api.example.com/v1", "https://127.0.0.1/v1", "https://169.254.169.254/latest"):
        assert c.post("/api/providers", json={"id": "bad", "base_url": url, "api_key": "12345678"}).status_code == 422


# ---------- brain: ranked, permission-aware, honest about semantic mode ----------
def test_keyword_search_ranks_and_respects_spaces_and_status(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    notes = c.get("/api/brain/notes").json()
    assert notes
    with pf.db() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(notes)")]
        base = dict(con.execute("SELECT * FROM notes LIMIT 1").fetchone())
        def add(i, title, body, space, status):
            d = dict(base, id=i, title=title, body=body, space=space, status=status, flags="[]")
            con.execute(f"INSERT INTO notes ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [d[k] for k in cols])
        add("t-ok", "Zebra protocol", "zebra quarantine procedure for shared agents", "shared", "verified")
        add("t-secret", "Zebra secret", "zebra private finance space note", "finance", "verified")
        add("t-draft", "Zebra draft", "zebra unreviewed ai text", "shared", "draft")
        shared = brain.search_rows(con, "zebra", ("shared",), 10)
        assert [r["id"] for r in shared] == ["t-ok"]  # other space and unverified notes never come back
        assert {r["id"] for r in brain.search_rows(con, "zebra", ("shared", "finance"), 10)} == {"t-ok", "t-secret"}
        assert {r["id"] for r in brain.search_rows(con, "zebra", ("shared",), 10, ("verified", "draft"))} == {"t-ok", "t-draft"}
        assert brain.search_rows(con, "!!!", ("shared",), 5) == [] and brain.search_rows(con, "zebra", (), 5) == []
        con.execute("UPDATE notes SET body='zebra renamed' WHERE id='t-ok'")  # the index follows edits
        assert brain.search_rows(con, "quarantine", ("shared",), 5) == []
        con.execute("DELETE FROM notes WHERE id='t-ok'")
        assert brain.search_rows(con, "zebra", ("shared",), 5) == []


def test_search_api_enforces_agent_spaces(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    bots = {b["name"]: b for b in c.get("/api/bots").json()}
    with pf.db() as con:
        cols = [r[1] for r in con.execute("PRAGMA table_info(notes)")]
        base = dict(con.execute("SELECT * FROM notes LIMIT 1").fetchone())
        d = dict(base, id="t-fin", title="Quokka limits", body="quokka payment limits finance only", space="space-that-nobody-has", status="verified", flags="[]")
        con.execute(f"INSERT INTO notes ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [d[k] for k in cols])
    scout = bots["Scout"]["id"]
    r = c.get("/api/brain/search", params={"q": "quokka", "agent": scout}).json()
    assert r["results"] == [] and r["mode"] == "keyword" and r["semantic_configured"] is False
    assert [x["id"] for x in c.get("/api/brain/search", params={"q": "quokka"}).json()["results"]] == ["t-fin"]  # an admin sees every space
    with pf.db() as con:
        con.execute("UPDATE bots SET status='suspended' WHERE id=?", (scout,))
    assert c.get("/api/brain/search", params={"q": "quokka", "agent": scout}).status_code == 403


def test_hybrid_fusion_math():
    ranked = brain.fuse({"a": 10, "b": 5}, {"b": 0.9, "c": 0.8}, alpha=0.5)
    assert [i for i, _ in ranked][0] in ("a", "b") and dict(ranked)["b"] > dict(ranked)["c"]
    assert brain.fuse({}, {}) == [] and brain.fuse({"x": 3}, {})[0] == ("x", 0.5)
    assert abs(brain.cosine([1, 0], [1, 0]) - 1) < 1e-9 and brain.cosine([1, 0], [0, 1]) == 0 and brain.cosine([0, 0], [1, 1]) == 0


def test_semantic_mode_is_reported_only_when_it_really_ran(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k" * 12)
    monkeypatch.setenv("CFA_EMBEDDING_MODEL", "embed-test")

    def handler(req):
        inputs = json.loads(req.content)["input"]
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [1.0, 0.0] if "payment" in t.lower() else [0.0, 1.0]} for i, t in enumerate(inputs)], "usage": {"prompt_tokens": 7}})

    llm_transport(monkeypatch, handler)
    assert c.post("/api/brain/reindex").json()["indexed"] > 0
    r = c.get("/api/brain/search", params={"q": "payment limits"}).json()
    assert r["mode"] == "hybrid" and r["results"]
    llm_transport(monkeypatch, lambda req: httpx.Response(500))
    assert c.get("/api/brain/search", params={"q": "payment limits"}).json()["mode"] == "keyword"  # embedding provider down: say so
    assert any(m["calls"] and m["provider"] for m in c.get("/api/usage").json()["models"])


def test_reindex_without_embedding_model_is_honest(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.delenv("CFA_EMBEDDING_MODEL", raising=False)
    assert c.post("/api/brain/reindex").json()["semantic"] == "off"


# ---------- inventory accountability ----------
def test_inventory_flags_agents_without_accountable_humans(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A,mem:member:B")
    c.post("/api/demo/workspace", headers={"Authorization": "Bearer adm"})
    inv = {r["id"]: r for r in c.get("/api/inventory", headers={"Authorization": "Bearer adm"}).json()}
    assert "no_owner" in inv["strategist"]["accountability"] and "no_sponsor" in inv["strategist"]["accountability"]
    s0 = c.get("/api/inventory/summary", headers={"Authorization": "Bearer adm"}).json()
    assert s0["ownerless"] >= 4
    h = {"Authorization": "Bearer mem"}
    assert c.patch("/api/bots/strategist/accountability", json={"owner": "Ada"}, headers=h).status_code == 403
    r = c.patch("/api/bots/strategist/accountability", json={"owner": "Ada", "sponsor": "Bo", "purpose": "Frames decisions for the founders"}, headers={"Authorization": "Bearer adm"})
    assert r.status_code == 200 and r.json()["gaps"] == []
    assert c.get("/api/inventory/summary", headers={"Authorization": "Bearer adm"}).json()["ownerless"] == s0["ownerless"] - 1
    assert c.patch("/api/bots/nope/accountability", json={"owner": "x"}, headers={"Authorization": "Bearer adm"}).status_code == 404
    assert c.patch("/api/bots/strategist/accountability", json={}, headers={"Authorization": "Bearer adm"}).status_code == 422


# ---------- channels ----------
def test_channels_answer_only_when_mentioned_and_label_demo(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    team = c.get("/api/teams").json()[0]
    chans = c.get(f"/api/teams/{team['id']}/channels").json()
    assert [x["name"] for x in chans] == ["general"]
    cid = chans[0]["id"]
    assert c.post(f"/api/teams/{team['id']}/channels", json={"name": "decisions", "topic": "Calls"}).status_code == 201
    assert c.post(f"/api/teams/{team['id']}/channels", json={"name": "decisions"}).status_code == 409
    assert c.post(f"/api/teams/{team['id']}/channels", json={"name": "Bad Name"}).status_code == 422
    quiet = c.post(f"/api/channels/{cid}/messages", json={"content": "just a note to the humans"}).json()["messages"]
    assert [m.get("author_kind") for m in quiet if "author_kind" in m] == ["human"] and any("hint" in m for m in quiet)
    members = [b for b in c.get("/api/bots").json() if b["team"] == team["name"]]
    name = members[0]["name"]
    r = c.post(f"/api/channels/{cid}/messages", json={"content": f"@{name} what do you think?"}).json()["messages"]
    agent = [m for m in r if m.get("author_kind") == "agent"][0]
    assert agent["mode"] == "demo" and agent["content"].startswith("DEMO") and agent["author_name"] == name
    assert [m["author_kind"] for m in c.get(f"/api/channels/{cid}/messages").json()] == ["human", "human", "agent"]
    c.post(f"/api/bots/{members[0]['id']}/status", json={"status": "suspended", "reason": "test"})
    r2 = c.post(f"/api/channels/{cid}/messages", json={"content": f"@{name} again"}).json()["messages"]
    assert [m["author_kind"] for m in r2 if "author_kind" in m][-1] == "system"
    assert c.get("/api/channels/missing/messages").status_code == 404


def test_channel_live_reply_uses_the_agents_own_model(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k" * 12)
    team = c.get("/api/teams").json()[0]
    cid = c.get(f"/api/teams/{team['id']}/channels").json()[0]["id"]
    member = [b for b in c.get("/api/bots").json() if b["team"] == team["name"]][0]
    c.put(f"/api/bots/{member['id']}/model", json={"model": "channel-model"})
    seen = []
    llm_transport(monkeypatch, lambda req: (seen.append(json.loads(req.content)["model"]), ok())[1])
    m = [x for x in c.post(f"/api/channels/{cid}/messages", json={"content": f"@{member['name']} hello"}).json()["messages"] if x.get("author_kind") == "agent"][0]
    assert seen == ["channel-model"] and m["mode"] == "live"
    assert c.get("/api/usage").json()["by_kind"]["channel"] == 1


# ---------- computer use ----------
def test_computer_use_is_reported_unconfigured_and_refuses_sessions(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    s = c.get("/api/computer-use/status").json()
    assert s["status"] == "unconfigured" and s["problems"] and "application server" in s["note"]
    monkeypatch.setenv("CFA_COMPUTER_USE", "1")
    assert c.get("/api/computer-use/status").json()["status"] == "unconfigured"  # flag alone is not enough: a provider must be registered
    assert c.post("/api/computer-use/sessions").status_code == 501


# ---------- secrets never reach the log ----------
def test_failed_model_call_does_not_leak_the_key(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    key = "sk-LEAKCHECK-987654321"
    monkeypatch.setenv("CFA_MODEL_API_KEY", key)
    llm_transport(monkeypatch, lambda req: httpx.Response(401, json={"error": key}))
    r = ask(c)
    assert r.status_code in (401, 402, 429, 502) and key not in r.text
    with pf.db() as con:
        dump = json.dumps([dict(x) for x in con.execute("SELECT * FROM llm_usage")])
    assert key not in dump and "rejected the API key" in dump
