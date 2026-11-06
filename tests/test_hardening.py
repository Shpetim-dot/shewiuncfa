"""Production hardening: headers, docs lockdown, origin checks, no user enumeration."""
import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app import main
from app import ratelimit

PASS = "correct-horse-battery-staple-42"


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("cfa_csrf", "")}


def fresh(tmp_path, monkeypatch, **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "h.db")
    for key in ("CFA_API_KEYS", "CFA_ENV", "CFA_BILLING", "CFA_PLAN", "CFA_RATELIMIT",
                "CFA_PUBLIC_DOCS", "CFA_ALLOW_SIGNUP", "APP_URL"):
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


def test_security_headers_on_every_response(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    register(c)
    r = c.get("/api/bots")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["cross-origin-opener-policy"] == "same-origin"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"
    assert r.headers["x-permitted-cross-domain-policies"] == "none"
    assert "camera=()" in r.headers["permissions-policy"]
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]


def test_interactive_docs_are_off_in_production(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    register(c)
    assert c.get("/docs").status_code == 200  # development keeps them
    monkeypatch.setenv("CFA_ENV", "production")
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert c.get(path).status_code == 404
    # the API itself keeps working
    assert c.get("/api/health").status_code == 200


def test_docs_can_be_enabled_explicitly(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_ENV="production", CFA_PUBLIC_DOCS="1", CFA_ALLOW_SIGNUP="1")
    assert c.get("/openapi.json").status_code == 200


def test_cookie_write_from_a_foreign_origin_is_rejected(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    register(c)
    body = {"title": "x", "body": "y"}
    ok = c.post("/api/brain/notes", json=body, headers={**csrf(c), "Origin": "https://evil.example"})
    assert ok.status_code == 403 and "origin" in ok.json()["detail"]
    # no Origin header (CLI, same-origin fetch without it) still works with CSRF
    assert c.post("/api/brain/notes", json=body, headers=csrf(c)).status_code == 201


def test_bearer_clients_are_not_origin_checked(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    token = register(c)["token"]
    other = TestClient(main.app)
    r = other.post("/api/brain/notes", json={"title": "b", "body": "b"},
                   headers={"Authorization": f"Bearer {token}", "Origin": "https://evil.example"})
    assert r.status_code == 201


def test_login_does_not_reveal_whether_an_account_exists(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    register(c)
    fresh_client = TestClient(main.app)
    known = fresh_client.post("/api/auth/login", json={"email": "a@acme.example", "password": "wrong-password-1"})
    unknown = fresh_client.post("/api/auth/login", json={"email": "ghost@acme.example", "password": "wrong-password-1"})
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()  # identical answer, no enumeration signal
