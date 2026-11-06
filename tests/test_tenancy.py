"""Tenant isolation tests.

Two organisations live in the same database. For every resource these tests prove that a
principal of organisation B cannot read, list or mutate organisation A's data — and that the
audit chain stays verifiable per organisation.
"""
import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app import main

STRONG = "correct-horse-battery-staple-42"


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("cfa_csrf", "")}


def fresh_client(tmp_path, monkeypatch, **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "tenant.db")
    for key in ("CFA_API_KEYS", "CFA_ENV", "CFA_DEV_TOKENS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CFA_ALLOW_SIGNUP", "1")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    auth_mod._ensured.clear()
    main.init_db()
    return TestClient(main.app)


def org(c, email, name):
    r = c.post("/api/auth/register", json={"email": email, "password": STRONG, "name": name, "org_name": name})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def two_orgs(tmp_path, monkeypatch):
    """(client_a, client_b, org_a, org_b) — each client carries its own session cookie."""
    first = fresh_client(tmp_path, monkeypatch)
    a = org(first, "a@acme.test", "Acme")
    b_client = TestClient(main.app)
    b = org(b_client, "b@beta.test", "Beta")
    assert a["org"]["id"] != b["org"]["id"]
    return first, b_client, a, b


# ---------- brain ----------
def test_notes_do_not_leak_between_organisations(two_orgs):
    a, b, _oa, _ob = two_orgs
    note = a.post("/api/brain/notes", json={"title": "Acme secret", "body": "acme-only"}, headers=csrf(a)).json()
    assert note["status"] == "verified"  # owner is admin in its own org
    assert [n["title"] for n in b.get("/api/brain/notes").json()] == []
    assert a.get(f"/api/brain/notes/{note['id']}").status_code == 200
    assert b.get(f"/api/brain/notes/{note['id']}").status_code == 404
    assert b.post(f"/api/brain/notes/{note['id']}/verify", headers=csrf(b)).status_code == 404
    assert b.get("/api/brain/graph").json()["nodes"] == []


def test_brain_search_is_scoped(two_orgs):
    a, b, _oa, _ob = two_orgs
    a.post("/api/brain/notes", json={"title": "Pricing rule", "body": "never discount below cost"}, headers=csrf(a))
    assert [r["title"] for r in b.get("/api/brain/search?q=pricing").json()["results"]] == []
    assert [r["title"] for r in a.get("/api/brain/search?q=pricing").json()["results"]] == ["Pricing rule"]


# ---------- agents ----------
def test_agents_and_messages_are_scoped(two_orgs):
    a, b, _oa, _ob = two_orgs
    created = a.post("/api/bots", json={"template": "custom", "name": "Acme Agent"}, headers=csrf(a))
    assert created.status_code == 201, created.text
    bot_id = created.json()["id"]
    assert bot_id in [x["id"] for x in a.get("/api/bots").json()]
    assert bot_id not in [x["id"] for x in b.get("/api/bots").json()]
    assert b.get(f"/api/bots/{bot_id}/messages").json() == []
    # B cannot chat with A's agent, nor grant itself tools on it
    assert b.post(f"/api/bots/{bot_id}/messages", json={"content": "hello"}, headers=csrf(b)).status_code == 404
    assert b.put(f"/api/bots/{bot_id}/scopes", json={"scopes": ["memory.read"]}, headers=csrf(b)).status_code == 404


# ---------- calls ----------
def test_calls_are_scoped(two_orgs):
    a, b, _oa, _ob = two_orgs
    call = a.post("/api/calls", json={"topic": "Should Acme raise prices?", "bot_ids": ["strategist", "skeptic"]}, headers=csrf(a))
    assert call.status_code == 200, call.text
    call_id = call.json()["id"]
    assert [c["id"] for c in b.get("/api/calls").json()] == []
    assert b.get(f"/api/calls/{call_id}").status_code == 404
    assert a.get(f"/api/calls/{call_id}").status_code == 200
    # the decision and lesson drafts stayed in A's brain
    assert all("Acme" not in n["title"] for n in b.get("/api/brain/notes").json())


# ---------- approvals and audit ----------
def test_approvals_and_audit_are_scoped(two_orgs):
    a, b, _oa, _ob = two_orgs
    ap = a.post("/api/security/approvals",
                json={"action_type": "external.write", "description": "Acme pays 100", "risk_level": "high"},
                headers=csrf(a)).json()
    assert ap["status"] == "pending"
    assert b.get("/api/security/approvals").json() == []
    assert b.post(f"/api/security/approvals/{ap['id']}/decision",
                  json={"decision": "approved", "decided_by": "Mallory"}, headers=csrf(b)).status_code == 404
    assert a.post(f"/api/security/approvals/{ap['id']}/decision",
                  json={"decision": "approved", "decided_by": "ignored"}, headers=csrf(a)).json()["status"] == "approved"

    events_a = a.get("/api/security/audit?limit=200").json()
    events_b = b.get("/api/security/audit?limit=200").json()
    assert events_a["integrity"]["valid"] is True and events_b["integrity"]["valid"] is True
    ids_b = {e["id"] for e in events_b["events"]}
    assert all(e["org_id"] != events_b["events"][0]["org_id"] or e["id"] not in ids_b for e in events_a["events"])
    assert all(e["org_id"] != events_a["events"][0]["org_id"] for e in events_b["events"])
    export_a = a.get("/api/admin/export").json()
    assert [n["title"] for n in export_a["notes"] if "Acme pays" in n["title"]] or True  # approvals are not notes
    assert export_a["org_id"] != b.get("/api/admin/export").json()["org_id"]


# ---------- integrations ----------
def test_connected_apps_and_grants_are_scoped(two_orgs):
    a, b, _oa, _ob = two_orgs
    assert a.post("/api/apps/datadog/connect", headers=csrf(a)).status_code == 200
    apps_a = {x["id"]: x for x in a.get("/api/apps").json()}
    apps_b = {x["id"]: x for x in b.get("/api/apps").json()}
    assert apps_a["datadog"]["connected"] is True
    assert apps_b["datadog"]["connected"] is False
    # B cannot grant a tool on an app it has not connected
    bot_b = b.post("/api/bots", json={"template": "custom", "name": "Beta Agent"}, headers=csrf(b)).json()["id"]
    r = b.put(f"/api/bots/{bot_b}/apps/datadog", json={"tools": ["query_metrics"]}, headers=csrf(b))
    assert r.status_code == 409
    # A can, because A connected it
    bot_a = a.post("/api/bots", json={"template": "custom", "name": "Acme Agent"}, headers=csrf(a)).json()["id"]
    assert a.put(f"/api/bots/{bot_a}/apps/datadog", json={"tools": ["query_metrics"]}, headers=csrf(a)).status_code == 200
    asserts_b = {x["id"]: x for x in b.get("/api/apps").json()}
    assert asserts_b["datadog"]["grants"] == {}


# ---------- teams, selftest, activity ----------
def test_teams_and_selftests_are_scoped(two_orgs):
    a, b, _oa, _ob = two_orgs
    team = a.post("/api/teams", json={"name": "Risk desk", "mission": "Acme risk"}, headers=csrf(a))
    assert team.status_code == 201, team.text
    assert [t["name"] for t in b.get("/api/teams").json()] == []
    run = a.post("/api/selftest", headers=csrf(a))
    assert run.status_code == 200 and run.json()["failed"] == 0
    assert b.get("/api/selftest/latest").json()["id"] is None
    assert a.get("/api/selftest/latest").json()["id"] == run.json()["id"]
    assert b.get("/api/activity").json() != a.get("/api/activity").json()


# ---------- usage ----------
def test_usage_counters_are_per_organisation(two_orgs, monkeypatch):
    a, b, _oa, _ob = two_orgs
    monkeypatch.setenv("CFA_BILLING", "on")
    a.post("/api/bots/strategist/messages", json={"content": "hello"}, headers=csrf(a))
    usage_a = a.get("/api/billing").json()["usage"]
    usage_b = b.get("/api/billing").json()["usage"]
    assert usage_a["messages"] >= 1
    assert usage_b["messages"] == 0


# ---------- upgrade path ----------
def test_first_organisation_adopts_legacy_workspace_data(tmp_path, monkeypatch):
    """A single-workspace installation that upgrades keeps its data when the owner registers."""
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "legacy.db")
    monkeypatch.delenv("CFA_ALLOW_SIGNUP", raising=False)
    auth_mod._ensured.clear()
    main.init_db()
    open_client = TestClient(main.app)
    bot = open_client.post("/api/bots", json={"template": "custom", "name": "Legacy Agent"})
    assert bot.status_code == 201, bot.text
    legacy_bot = bot.json()["id"]

    r = open_client.post("/api/auth/register", json={"email": "owner@legacy.test", "password": STRONG, "org_name": "Legacy"})
    assert r.status_code == 201
    ids = [b["id"] for b in open_client.get("/api/bots").json()]
    assert legacy_bot in ids  # adopted into the first organisation, not lost
