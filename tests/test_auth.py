"""Authentication, session, role and organisation tests.

These tests are the security contract of the product: they are expected to fail loudly
if anyone loosens authentication, drops the CSRF check, or lets a principal cross an
organisation boundary.
"""
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app import main

STRONG = "correct-horse-battery-staple-42"


def client(tmp_path, monkeypatch, **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "auth.db")
    for key in ("CFA_API_KEYS", "CFA_ENV", "CFA_ALLOW_SIGNUP", "CFA_DEV_TOKENS",
                "CFA_REQUIRE_EMAIL_VERIFICATION", "CFA_AUTH_ATTEMPTS", "CFA_AUTH_LOCKOUT_AFTER"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    auth_mod._ensured.clear()
    main.init_db()
    return TestClient(main.app)


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("cfa_csrf", "")}


def register(c, email="owner@example.com", org="Acme", password=STRONG, name="Owner"):
    return c.post("/api/auth/register", json={"email": email, "password": password, "name": name, "org_name": org})


# ---------- bootstrap ----------
def test_fresh_install_reports_setup_and_allows_only_bootstrap(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    status = c.get("/api/auth/status").json()
    assert status["setup_required"] is True and status["auth_required"] is False
    assert status["hash"] in ("argon2id", "pbkdf2-sha256")
    # No identity configured: the workspace is reachable (open dev mode, not production).
    assert c.get("/api/bots").status_code == 200


def test_first_registration_creates_organisation_and_owner(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    r = register(c)
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "owner" and body["user"]["email"] == "owner@example.com"
    assert body["org"]["name"] == "Acme"
    assert body["token"] and body["csrf"]
    assert c.cookies.get("cfa_session")
    me = c.get("/api/auth/me").json()
    assert me["user"]["email"] == "owner@example.com" and me["org"]["slug"] == "acme"


def test_weak_password_is_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert register(c, password="short").status_code == 422


def test_duplicate_email_is_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_ALLOW_SIGNUP="1")
    assert register(c).status_code == 201
    assert register(c, org="Other").status_code == 409


def test_signup_closes_after_first_user_unless_enabled(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert register(c).status_code == 201
    r = register(c, email="second@example.com", org="Other")
    assert r.status_code == 403
    assert "invitation" in r.json()["detail"]


# ---------- fail closed ----------
def test_anonymous_access_is_rejected_once_a_user_exists(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    anon = TestClient(main.app)  # no cookies
    assert anon.get("/api/bots").status_code == 401
    assert anon.get("/api/admin/export").status_code == 401
    assert anon.get("/api/leads").status_code == 401
    assert anon.get("/api/security/audit").status_code == 401
    # public endpoints stay public
    assert anon.get("/api/health").status_code == 200
    assert anon.get("/api/auth/status").status_code == 200
    assert anon.post("/api/leads", json={"name": "Ann", "email": "a@b.co"}).status_code == 201


def test_production_without_identity_refuses_requests(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_ENV="production", CFA_ALLOW_SIGNUP="1")
    assert c.get("/api/bots").status_code == 503
    status = c.get("/api/health").json()
    assert status["auth"] == "disabled" and any("Authentication" in w for w in status["warnings"])


# ---------- login ----------
def test_login_with_correct_password_issues_a_session(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    fresh = TestClient(main.app)
    assert fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": STRONG}).status_code == 200
    assert fresh.get("/api/bots").status_code == 200


def test_login_with_wrong_password_fails_without_leaking(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    fresh = TestClient(main.app)
    r = fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": "nope-nope-nope"})
    assert r.status_code == 401 and r.json()["detail"] == "email or password is incorrect"
    r = fresh.post("/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"})
    assert r.status_code == 401 and r.json()["detail"] == "email or password is incorrect"


def test_account_locks_after_repeated_failures(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_AUTH_LOCKOUT_AFTER="3")
    register(c)
    fresh = TestClient(main.app)
    for _ in range(3):
        fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": "bad-password-here"})
    r = fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": STRONG})
    assert r.status_code == 429
    assert "locked" in r.json()["detail"]


def test_login_is_rate_limited_per_ip(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_AUTH_ATTEMPTS="3")
    register(c)
    fresh = TestClient(main.app)
    codes = [fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": "bad"}).status_code
             for _ in range(4)]
    assert 429 in codes


# ---------- csrf ----------
def test_cookie_auth_requires_csrf_header(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    blocked = c.post("/api/brain/notes", json={"title": "x", "body": "y"})
    assert blocked.status_code == 403 and "CSRF" in blocked.json()["detail"]
    ok = c.post("/api/brain/notes", json={"title": "x", "body": "y"}, headers=csrf(c))
    assert ok.status_code == 201


def test_bearer_session_token_needs_no_csrf(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    token = register(c).json()["token"]
    fresh = TestClient(main.app)
    r = fresh.post("/api/brain/notes", json={"title": "bearer", "body": "body"},
                   headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201


def test_invalid_csrf_token_is_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    r = c.post("/api/brain/notes", json={"title": "x", "body": "y"}, headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403


# ---------- sessions ----------
def test_logout_revokes_the_session(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    token = register(c).json()["token"]
    assert c.post("/api/auth/logout", headers=csrf(c)).status_code == 200
    fresh = TestClient(main.app)
    assert fresh.get("/api/bots", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_sessions_are_listed_and_revocable(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    second = TestClient(main.app)
    second.post("/api/auth/login", json={"email": "owner@example.com", "password": STRONG})
    listed = c.get("/api/auth/sessions").json()
    assert len(listed) >= 2
    other = next(s for s in listed if not s["current"])
    assert c.delete(f"/api/auth/sessions/{other['id']}", headers=csrf(c)).status_code == 200


def test_expired_session_is_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    token = register(c).json()["token"]
    with auth_mod.db() as con:
        con.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    assert TestClient(main.app).get("/api/bots", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ---------- roles ----------
def test_owner_invites_a_developer_and_roles_are_enforced(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    inv = c.post("/api/org/invitations", json={"email": "dev@example.com", "role": "developer"}, headers=csrf(c))
    assert inv.status_code == 201
    token = inv.json()["token"]

    dev = TestClient(main.app)
    accepted = dev.post("/api/org/invitations/accept",
                        json={"token": token, "password": STRONG, "name": "Dev"})
    assert accepted.status_code == 201 and accepted.json()["user"]["role"] == "developer"
    assert dev.get("/api/bots").status_code == 200                                    # read allowed
    assert dev.get("/api/admin/export").status_code == 403                            # admin only
    assert dev.post("/api/org/invitations", json={"email": "x@y.co", "role": "admin"},
                    headers=csrf(dev)).status_code == 403
    # a developer may write, a viewer may not
    assert dev.post("/api/brain/notes", json={"title": "d", "body": "d"}, headers=csrf(dev)).status_code == 201


def test_viewer_is_read_only(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    inv = c.post("/api/org/invitations", json={"email": "view@example.com", "role": "viewer"}, headers=csrf(c)).json()
    viewer = TestClient(main.app)
    viewer.post("/api/org/invitations/accept", json={"token": inv["token"], "password": STRONG})
    assert viewer.get("/api/bots").status_code == 200
    assert viewer.post("/api/brain/notes", json={"title": "v", "body": "v"}, headers=csrf(viewer)).status_code == 403


def test_cannot_grant_a_role_above_your_own(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    inv = c.post("/api/org/invitations", json={"email": "admin2@example.com", "role": "admin"}, headers=csrf(c)).json()
    admin2 = TestClient(main.app)
    admin2.post("/api/org/invitations/accept", json={"token": inv["token"], "password": STRONG})
    assert admin2.post("/api/org/invitations", json={"email": "boss@example.com", "role": "owner"},
                       headers=csrf(admin2)).status_code == 403


def test_role_change_invalidates_sessions(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    inv = c.post("/api/org/invitations", json={"email": "dev@example.com", "role": "developer"}, headers=csrf(c)).json()
    dev = TestClient(main.app)
    accepted = dev.post("/api/org/invitations/accept", json={"token": inv["token"], "password": STRONG}).json()
    user_id = accepted["user"]["id"]
    assert dev.get("/api/bots").status_code == 200
    assert c.patch(f"/api/org/members/{user_id}", json={"role": "viewer"}, headers=csrf(c)).status_code == 200
    assert dev.get("/api/bots").status_code == 401


# ---------- organisations ----------
def test_members_are_scoped_to_their_organisation(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_ALLOW_SIGNUP="1")
    register(c)
    other = TestClient(main.app)
    r = other.post("/api/auth/register", json={"email": "b@example.com", "password": STRONG, "org_name": "Beta"})
    assert r.status_code == 201
    members_b = other.get("/api/org/members").json()["members"]
    members_a = c.get("/api/org/members").json()["members"]
    assert {m["email"] for m in members_b} == {"b@example.com"}
    assert {m["email"] for m in members_a} == {"owner@example.com"}
    a_user = members_a[0]["id"]
    # tenant A cannot see or modify tenant B's member
    assert c.patch(f"/api/org/members/{a_user}", json={"role": "viewer"}, headers=csrf(c)).status_code == 200
    assert other.delete(f"/api/org/members/{a_user}", headers=csrf(other)).status_code == 404


# ---------- password reset / verification ----------
def test_password_reset_flow_revokes_old_sessions(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    token = register(c).json()["token"]
    r = c.post("/api/auth/password/forgot", json={"email": "owner@example.com"})
    assert r.status_code == 200
    reset_token = r.json()["token"]
    fresh = TestClient(main.app)
    assert fresh.post("/api/auth/password/reset", json={"token": reset_token, "password": "new-password-1234"}).status_code == 200
    # old session gone, old password invalid, new password works
    assert fresh.get("/api/bots", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": STRONG}).status_code == 401
    assert fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": "new-password-1234"}).status_code == 200


def test_password_forgot_does_not_leak_accounts(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    a = c.post("/api/auth/password/forgot", json={"email": "owner@example.com"}).json()
    b = c.post("/api/auth/password/forgot", json={"email": "ghost@example.com"}).json()
    assert a == b == {"ok": True}


def test_reset_token_is_single_use(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    tok = c.post("/api/auth/password/forgot", json={"email": "owner@example.com"}).json()["token"]
    assert c.post("/api/auth/password/reset", json={"token": tok, "password": "first-password-1"}).status_code == 200
    assert c.post("/api/auth/password/reset", json={"token": tok, "password": "second-password-2"}).status_code == 400


def test_email_verification_flow(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    r = c.post("/api/auth/verify-email/resend", headers=csrf(c))
    assert r.status_code == 200 and "token" in r.json()
    assert c.post("/api/auth/verify-email", json={"token": r.json()["token"]}).status_code == 200
    assert c.get("/api/auth/me").json()["user"]["email_verified"] is True


def test_verification_can_be_required_for_login(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_REQUIRE_EMAIL_VERIFICATION="1")
    register(c)
    fresh = TestClient(main.app)
    r = fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": STRONG})
    assert r.status_code == 403 and "verify" in r.json()["detail"]


# ---------- audit ----------
def test_auth_events_are_audited(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    register(c)
    fresh = TestClient(main.app)
    fresh.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong-password-1"})
    types = [e["event_type"] for e in c.get("/api/security/audit?limit=50").json()["events"]]
    assert "org.created" in types and "auth.registered" in types and "auth.login_failed" in types


def test_legacy_api_keys_still_work(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, CFA_API_KEYS="tok123:admin:Alice")
    assert c.get("/api/bots").status_code == 401
    assert c.get("/api/bots", headers={"Authorization": "Bearer tok123"}).status_code == 200
    assert c.get("/api/bots", headers={"Authorization": "tok123"}).status_code == 200  # header without the prefix
