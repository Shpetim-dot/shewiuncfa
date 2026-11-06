"""Per-agent audit trail, revenue view and announcements."""
import json

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app import main

PASS = "correct-horse-battery-staple-42"


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("cfa_csrf", "")}


def fresh(tmp_path, monkeypatch, **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "extra.db")
    for key in ("CFA_API_KEYS", "CFA_ENV", "CFA_DEV_TOKENS", "CFA_BILLING", "CFA_PLAN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("CFA_ALLOW_SIGNUP", "1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    auth_mod._ensured.clear()
    main.init_db()
    return TestClient(main.app)


def owner(c, email="a@acme.example", org="Acme"):
    r = c.post("/api/auth/register", json={"email": email, "password": PASS, "name": "A", "org_name": org})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- per-agent audit ----------
def test_chat_writes_a_hash_linked_per_agent_trail(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    c.post("/api/bots/strategist/messages", json={"content": "Should we raise prices?"}, headers=csrf(c))
    data = c.get("/api/bots/strategist/audit").json()
    kinds = [e["kind"] for e in data["entries"]]
    assert "message" in kinds and "reply" in kinds
    assert data["integrity"]["valid"] is True and data["integrity"]["checked"] >= 2
    # newest first, and the chain links entry to entry
    newest, older = data["entries"][0], data["entries"][1]
    assert newest["prev_hash"] == older["hash"]
    assert data["total"] >= 2


def test_per_agent_trail_detects_tampering(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    c.post("/api/bots/skeptic/messages", json={"content": "What breaks first?"}, headers=csrf(c))
    assert c.get("/api/bots/skeptic/audit/verify").json()["valid"] is True
    with main.connect() as db:
        db.execute("UPDATE agent_audit SET summary='rewritten' WHERE bot_id='skeptic'")
    result = c.get("/api/bots/skeptic/audit/verify").json()
    assert result["valid"] is False and result["failed_entry_id"]


def test_per_agent_trail_is_organisation_scoped(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    c.post("/api/bots/builder/messages", json={"content": "Scope this"}, headers=csrf(c))
    other = TestClient(main.app)
    r = other.post("/api/auth/register", json={"email": "b@beta.example", "password": PASS, "org_name": "Beta"})
    assert r.status_code == 201
    assert other.get("/api/bots/builder/audit").json() == {"agent": "builder", "total": 0, "entries": [], "name": "Builder", "integrity": {"valid": True, "checked": 0, "head": "GENESIS", "agent": "builder"}}


def test_denied_tool_call_is_recorded(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    c.post("/api/apps/datadog/connect", headers=csrf(c))
    r = c.post("/api/bots/builder/tools", json={"app": "datadog", "tool": "query_metrics"}, headers=csrf(c))
    assert r.status_code == 403  # no grant
    kinds = [e["kind"] for e in c.get("/api/bots/builder/audit").json()["entries"]]
    assert "tool.denied" in kinds


def test_export_is_ndjson_with_the_same_entries(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    c.post("/api/bots/chair/messages", json={"content": "Wrap it up"}, headers=csrf(c))
    text = c.get("/api/bots/chair/audit/export").text
    lines = [json.loads(x) for x in text.strip().splitlines()]
    assert lines and len(lines) == c.get("/api/bots/chair/audit").json()["total"]
    assert all("hash" in x and "prev_hash" in x for x in lines)


# ---------- revenue ----------
def test_revenue_reflects_plan_and_seats(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_BILLING="on")
    owner(c)
    rev = c.get("/api/org/revenue").json()
    assert rev["plan"] == "free" and rev["mrr_eur"] == 0 and rev["seats"] == 1
    assert rev["currency"] == "EUR" and "note" in rev


def test_revenue_after_a_paid_plan(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_BILLING="on", STRIPE_WEBHOOK_SECRET="whsec_t",
              STRIPE_PRICE_PROFESSIONAL="price_pro")

    def sign(body, secret="whsec_t"):
        import hashlib, hmac, time
        t = int(time.time())
        sig = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
        return f"t={t},v1={sig}"

    ev = {"id": "evt_rev", "type": "checkout.session.completed",
          "data": {"object": {"mode": "subscription", "customer": "cus_9", "subscription": "sub_9",
                              "metadata": {"plan": "professional"}}}}
    body = json.dumps(ev).encode()
    assert c.post("/api/billing/webhook", content=body,
                  headers={"stripe-signature": sign(body), "content-type": "application/json"}).status_code == 200
    rev = c.get("/api/org/revenue").json()
    assert rev["plan"] == "professional" and rev["mrr_eur"] == 99 and rev["arr_eur"] == 1188


def test_operator_revenue_needs_super_admin(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_API_KEYS="ops:super_admin:Ops,adm:admin:Alice")
    assert c.get("/api/admin/revenue", headers={"Authorization": "Bearer adm"}).status_code == 403
    ok = c.get("/api/admin/revenue", headers={"Authorization": "Bearer ops"})
    assert ok.status_code == 200 and "mrr_eur" in ok.json()


# ---------- announcements ----------
def test_announcements_are_organisation_scoped(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    made = c.post("/api/announcements", json={"title": "Maintenance", "body": "Sunday 02:00 UTC",
                                              "level": "warning"}, headers=csrf(c))
    assert made.status_code == 201
    assert [a["title"] for a in c.get("/api/announcements").json()["announcements"]] == ["Maintenance"]
    other = TestClient(main.app)
    other.post("/api/auth/register", json={"email": "b@beta.example", "password": PASS, "org_name": "Beta"})
    assert other.get("/api/announcements").json()["announcements"] == []


def test_platform_announcement_needs_super_admin(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    assert c.post("/api/announcements", json={"title": "Platform notice", "body": "We shipped v9",
                                              "platform": True}, headers=csrf(c)).status_code == 403
    ops = TestClient(main.app)
    # without a configured key the operator request is simply unauthenticated
    assert ops.post("/api/announcements", json={"title": "Platform notice", "body": "We shipped v9",
                                                "platform": True}).status_code == 401
    monkeypatch.setenv("CFA_API_KEYS", "ops:super_admin:Ops")
    r = ops.post("/api/announcements", json={"title": "Platform notice", "body": "We shipped v9", "platform": True},
                 headers={"Authorization": "Bearer ops"})
    assert r.status_code == 201 and r.json()["platform"] is True
    assert [a["title"] for a in c.get("/api/announcements").json()["announcements"]] == ["Platform notice"]


def test_expired_announcements_disappear(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    owner(c)
    c.post("/api/announcements", json={"title": "Old news", "body": "gone soon", "expires_in_days": 1}, headers=csrf(c))
    with main.connect() as db:
        db.execute("UPDATE announcements SET expires_at='2000-01-01T00:00:00+00:00'")
    assert c.get("/api/announcements").json()["announcements"] == []
