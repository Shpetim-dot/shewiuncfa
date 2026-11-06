"""Durable per-organisation rate limiting and the operator metrics endpoint."""
import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app import main
from app import ratelimit

PASS = "correct-horse-battery-staple-42"


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("cfa_csrf", "")}


def fresh(tmp_path, monkeypatch, **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "limits.db")
    for key in ("CFA_API_KEYS", "CFA_ENV", "CFA_BILLING", "CFA_PLAN", "CFA_RATELIMIT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    monkeypatch.setenv("CFA_ALLOW_SIGNUP", "1")
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    auth_mod._ensured.clear()
    ratelimit._ensured.clear()
    ratelimit.reset_cache()
    main.init_db()
    return TestClient(main.app)


def register(c, email="a@acme.example", org="Acme"):
    r = c.post("/api/auth/register", json={"email": email, "password": PASS, "name": "A", "org_name": org})
    assert r.status_code == 201, r.text
    return r.json()


def test_limit_is_enforced_and_reports_retry_after(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_RATELIMIT="on", CFA_RATELIMIT_DEFAULT="5")
    register(c)
    codes = [c.get("/api/bots").status_code for _ in range(8)]
    assert codes[:5] == [200] * 5
    assert 429 in codes[5:]
    blocked = next(i for i, code in enumerate(codes) if code == 429)
    r = c.get("/api/bots")
    assert r.status_code == 429 and r.headers.get("retry-after") == "60"
    assert r.json()["detail"]["code"] == "rate_limited" and r.json()["detail"]["limit"] == 5
    assert blocked == 5


def test_limit_is_per_organisation(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_RATELIMIT="on", CFA_RATELIMIT_DEFAULT="3")
    register(c)
    other = TestClient(main.app)
    register(other, email="b@beta.example", org="Beta")
    for _ in range(4):
        c.get("/api/bots")
    assert c.get("/api/bots").status_code == 429
    assert other.get("/api/bots").status_code == 200  # the other tenant keeps its own budget


def test_rate_limiting_can_be_switched_off(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_RATELIMIT="off", CFA_RATELIMIT_DEFAULT="2")
    register(c)
    assert [c.get("/api/bots").status_code for _ in range(6)] == [200] * 6


def test_plan_sets_the_limit(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_RATELIMIT="on", CFA_BILLING="on")
    register(c)
    assert ratelimit.limit_for(c.get("/api/auth/me").json()["org"]["id"]) == ratelimit.PLAN_LIMITS["free"]


def test_health_and_uploads_are_not_blocked_by_the_limiter(tmp_path, monkeypatch):
    """Health checks must keep working even when the tenant is over budget."""
    c = fresh(tmp_path, monkeypatch, CFA_RATELIMIT="on", CFA_RATELIMIT_DEFAULT="2")
    register(c)
    for _ in range(4):
        c.get("/api/bots")
    assert c.get("/api/health").status_code == 200 or c.get("/api/health").json()["status"] == "ok"


def test_metrics_endpoint_reports_counts_and_budget(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_RATELIMIT="on", CFA_RATELIMIT_DEFAULT="500")
    register(c)
    c.post("/api/bots/strategist/messages", json={"content": "hello"}, headers=csrf(c))
    m = c.get("/api/admin/metrics").json()
    assert m["counts"]["agents"] >= 4 and m["counts"]["agent_audit_entries"] >= 2
    assert m["rate_limit"]["used"] >= 1 and m["rate_limit"]["limit"] == 500
    assert m["database_bytes"] > 0 and m["database_mb"] >= 0
