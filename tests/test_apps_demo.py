from fastapi.testclient import TestClient

from app import main


def client(tmp_path, monkeypatch, keys=""):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "a.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("CFA_API_KEYS", keys)
    main.init_db()
    return TestClient(main.app)


def test_demo_workspace_is_rich_idempotent_and_removable(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    first = c.post("/api/demo/workspace").json()
    assert first["agents"] == 4 and first["notes"] >= 15
    assert c.post("/api/demo/workspace").json()["notes"] == 0
    g = c.get("/api/brain/graph").json()
    assert len(g["nodes"]) >= 15 and len(g["edges"]) >= 25
    assert {b["team"] for b in c.get("/api/bots").json()} >= {"Council", "Finance desk", "Research", "Support"}
    assert all(n["preview"] for n in c.get("/api/brain/notes").json())
    c.delete("/api/demo/workspace")
    assert not [n for n in c.get("/api/brain/notes").json() if n["source"] == "demo"]
    assert "Ledger" not in {b["name"] for b in c.get("/api/bots").json()}


def test_tool_governance(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    bots = {b["name"]: b["id"] for b in c.get("/api/bots").json()}
    read = c.post(f"/api/bots/{bots['Scout']}/tools", json={"app": "notion", "tool": "search_pages"}).json()
    assert read["status"] == "completed" and "No external service" in read["result"]
    write = c.post(f"/api/bots/{bots['Nova']}/tools", json={"app": "atlassian", "tool": "create_issue"}).json()
    assert write["status"] == "pending_approval" and write["approval"]["status"] == "pending"
    assert c.post(f"/api/bots/{bots['Ledger']}/tools", json={"app": "atlassian", "tool": "create_issue"}).status_code == 403
    assert c.post(f"/api/bots/{bots['Scout']}/tools", json={"app": "sentry", "tool": "list_issues"}).status_code == 409
    c.post("/api/apps/1password/connect")
    assert c.put(f"/api/bots/{bots['Scout']}/apps/1password", json={"tools": ["read_secret"]}).status_code == 422
    assert c.post(f"/api/bots/{bots['Scout']}/tools", json={"app": "1password", "tool": "read_secret"}).status_code == 403
    types = [e["event_type"] for e in c.get("/api/security/audit?limit=60").json()["events"]]
    assert "tool.call" in types and "tool.pending" in types and "agent.denied" in types


def test_app_changes_are_admin_only(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A,mem:member:B")
    h = lambda t: {"Authorization": f"Bearer {t}"}
    assert c.post("/api/apps/notion/connect", headers=h("mem")).status_code == 403
    assert c.post("/api/apps/notion/connect", headers=h("adm")).json()["connected"] is True
    assert c.put("/api/bots/builder/apps/notion", json={"tools": ["search_pages"]}, headers=h("mem")).status_code == 403
    assert c.put("/api/bots/builder/apps/notion", json={"tools": ["search_pages"]}, headers=h("adm")).status_code == 200


def test_selftest_covers_tools_on_demo_workspace(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/demo/workspace")
    r = c.post("/api/selftest").json()
    assert r["failed"] == 0 and r["passed"] > 90
    assert any("needs human approval" in p["name"] for p in r["probes"])


def test_call_returns_plan_with_owners_from_participants(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = c.post("/api/calls", json={"topic": "Pilot supplier payments", "bot_ids": ["strategist", "skeptic", "builder"]}).json()
    assert len(r["plan"]) >= 3 and {p["owner"] for p in r["plan"]} <= {"Strategist", "Skeptic", "Builder"}
    assert c.get(f"/api/calls/{r['id']}").json()["plan"] == r["plan"]


def test_create_agent_with_icon_team_color(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    b = c.post("/api/bots", json={"template": "research-analyst", "name": "Atlas", "icon": "book", "team": "Research", "color": "#3D7A4F"}).json()
    assert b["id"] == "atlas"
    listed = {x["id"]: x for x in c.get("/api/bots").json()}["atlas"]
    assert listed["icon"] == "book" and listed["team"] == "Research"
    assert c.post("/api/bots", json={"template": "custom", "name": "Bad", "icon": "skull"}).status_code == 422
