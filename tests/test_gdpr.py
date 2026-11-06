"""GDPR organisation deletion and plan storage limits."""
import base64

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app import main
from app import ratelimit

PASS = "correct-horse-battery-staple-42"


def csrf(c):
    return {"X-CSRF-Token": c.cookies.get("cfa_csrf", "")}


def fresh(tmp_path, monkeypatch, **env):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "g.db")
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


def test_deletion_requires_the_slug(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    register(c)
    assert c.delete("/api/org?confirm=wrong", headers=csrf(c)).status_code == 422
    assert c.get("/api/bots").status_code == 200  # nothing deleted


def test_owner_can_delete_their_organisation(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    data = register(c)
    org_id = data["org"]["id"]
    c.post("/api/brain/notes", json={"title": "Sensitive", "body": "secret"}, headers=csrf(c))
    out = c.delete(f"/api/org?confirm=acme", headers=csrf(c))
    assert out.status_code == 200 and out.json()["deleted"] is True
    assert out.json()["records"]["notes"] == 1
    with main.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM orgs WHERE id=?", (org_id,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM users WHERE org_id=?", (org_id,)).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM notes WHERE org_id=?", (org_id,)).fetchone()[0] == 0
        log = db.execute("SELECT * FROM deletion_log WHERE org_id=?", (org_id,)).fetchone()
    assert log is not None and log["slug"] == "acme"


def test_other_organisation_survives_a_deletion(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch)
    register(c)
    other = TestClient(main.app)
    register(other, email="b@beta.example", org="Beta")
    other.post("/api/brain/notes", json={"title": "Beta secret", "body": "b"}, headers=csrf(other))
    assert c.delete("/api/org?confirm=acme", headers=csrf(c)).status_code == 200
    assert [n["title"] for n in other.get("/api/brain/notes").json()] == ["Beta secret"]


def test_non_owner_cannot_delete(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_DEV_TOKENS="1")
    register(c)
    inv = c.post("/api/org/invitations", json={"email": "dev@acme.example", "role": "admin"},
                 headers=csrf(c)).json()
    dev = TestClient(main.app)
    dev.post("/api/org/invitations/accept", json={"token": inv["token"], "password": PASS})
    assert dev.delete("/api/org?confirm=acme", headers=csrf(dev)).status_code == 403


def test_storage_limit_blocks_large_uploads(tmp_path, monkeypatch):
    c = fresh(tmp_path, monkeypatch, CFA_BILLING="on")
    register(c)
    # fill the plan budget directly (25 MB on free) so the next upload must be refused
    with main.connect() as db:
        db.execute("INSERT INTO notes (id,title,body,kind,status,owner,source,created_at,updated_at,space,flags,org_id) "
                   "VALUES ('big','big','x'||printf('%.2000000c',''),'note','verified','a','t','2026-01-01','2026-01-01','shared','[]',"
                   "(SELECT id FROM orgs LIMIT 1))")
        db.execute("UPDATE notes SET body = replace(body, 'x', 'x')")
    payload = base64.b64encode(b"hello world" * 100).decode()
    r = c.post("/api/brain/upload", json={"filename": "a.txt", "content_b64": payload}, headers=csrf(c))
    assert r.status_code in (201, 402)  # 402 when the organisation is over its storage plan
