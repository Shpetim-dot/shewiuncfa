from fastapi.testclient import TestClient

from app import main
from app.cfa_core import retrieve, db


def client(tmp_path, monkeypatch, keys=None):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "t.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("CFA_API_KEYS", keys or "")
    main.init_db()
    return TestClient(main.app)


def test_bots_seeded_and_chat_creates_draft(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert {b["id"] for b in c.get("/api/bots").json()} >= {"strategist", "skeptic", "builder", "chair"}
    r = c.post("/api/bots/strategist/messages", json={"content": "Should we launch?"}).json()
    assert r["mode"] == "demo" and r["reply"].startswith("DEMO")
    note = c.get(f"/api/brain/notes/{r['draft_note_id']}").json()
    assert note["status"] == "draft" and note["kind"] == "chat"


def test_call_runs_rounds_shows_changed_mind_and_drafts_memory(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/api/calls", json={"topic": "Launch a payments agent pilot", "bot_ids": ["strategist", "skeptic", "builder"], "rounds": 1}).json()
    assert {e["round"] for e in r["events"]} == {0, 1} and len(r["events"]) == 6
    assert r["map"]["Skeptic"] == ["oppose", "unsure"]
    assert any(e["revised"] for e in r["events"])
    assert "Pre-mortem" in r["decision"] and "Kill criteria" in r["decision"]
    notes = c.get("/api/brain/notes").json()
    assert len(r["draft_note_ids"]) == 4 and all(n["status"] == "draft" for n in notes)
    assert c.get(f"/api/calls/{r['id']}").json()["map"] == r["map"]
    assert c.get("/api/security/audit/verify").json()["valid"] is True


def test_calls_reject_unknown_duplicate_or_chair(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    for ids in (["strategist", "nope"], ["strategist", "strategist"], ["strategist", "chair"]):
        assert c.post("/api/calls", json={"topic": "A valid topic here", "bot_ids": ids}).status_code == 422


def test_only_verified_notes_reach_retrieval(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    n = c.post("/api/bots/skeptic/messages", json={"content": "payments pilot limits"}).json()["draft_note_id"]
    with db() as con:
        assert retrieve(con, "payments pilot limits", spaces=("shared", "agent:skeptic")) == []
    c.post(f"/api/brain/notes/{n}/verify")
    with db() as con:
        assert len(retrieve(con, "payments pilot limits", spaces=("shared", "agent:skeptic"))) == 1


def test_wikilinks_backlinks_and_graph(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    a = c.post("/api/brain/notes", json={"title": "Spend cap", "body": "Hard cap per pilot."}).json()
    b = c.post("/api/brain/notes", json={"title": "Pilot rule", "body": "See [[Spend cap]]."}).json()
    assert c.get(f"/api/brain/notes/{a['id']}").json()["backlinks"] == ["Pilot rule"]
    g = c.get("/api/brain/graph").json()
    assert {"from": b["id"], "to": a["id"]} in g["edges"]


def test_auth_roles_and_server_side_approver(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:Alice,mem:member:Bob,view:viewer:Eve")
    h = lambda t: {"Authorization": f"Bearer {t}"}
    assert c.get("/api/bots").status_code == 401
    assert c.get("/api/health").json()["auth"] == "enabled"
    assert c.post("/api/bots/builder/messages", json={"content": "hi"}, headers=h("view")).status_code == 403
    n = c.post("/api/bots/builder/messages", json={"content": "hi there"}, headers=h("mem")).json()["draft_note_id"]
    assert c.post(f"/api/brain/notes/{n}/verify", headers=h("mem")).status_code == 403
    assert c.post(f"/api/brain/notes/{n}/verify", headers=h("adm")).json()["status"] == "verified"
    ap = c.post("/api/security/approvals", json={"action_type": "external.write", "description": "Send a payment", "risk_level": "high"}, headers=h("mem")).json()
    assert c.post(f"/api/security/approvals/{ap['id']}/decision", json={"decision": "approved", "decided_by": "Bob"}, headers=h("mem")).status_code == 403
    done = c.post(f"/api/security/approvals/{ap['id']}/decision", json={"decision": "approved", "decided_by": "Mallory"}, headers=h("adm")).json()
    assert done["decision_by"] == "Alice"


def test_rate_limit(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    monkeypatch.setenv("CFA_POSTS_PER_MINUTE", "2")
    from app import cfa_core as platform
    platform._hits.clear()
    codes = [c.post("/api/bots/builder/messages", json={"content": "x"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
