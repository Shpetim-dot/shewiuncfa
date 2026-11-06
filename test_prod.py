import json
import logging
import sqlite3

from fastapi.testclient import TestClient

from app import main


def client(tmp_path, monkeypatch, keys=""):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "p.db")
    for k in ("CFA_MODEL_API_KEY", "CFA_ENV", "CFA_SECRET_KEY", "CFA_ALLOW_TMP_DB"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CFA_API_KEYS", keys)
    monkeypatch.setenv("CFA_DEMO_DELAY", "0")
    main.init_db()
    return TestClient(main.app)


def test_database_keys_are_hashed_roles_work_and_last_admin_is_protected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)  # open dev mode: the first key switches protection on
    made = c.post("/api/admin/keys", json={"name": "Alice", "role": "admin"}).json()
    token = made["token"]
    assert token.startswith("cfa_") and "cannot be shown again" in made["warning"]
    assert c.get("/api/bots").status_code == 401
    h = {"Authorization": f"Bearer {token}"}
    assert c.get("/api/bots", headers=h).status_code == 200
    raw = sqlite3.connect(main.DB_PATH).execute("SELECT name,role,token_hash,created_by FROM api_keys").fetchall()
    assert token not in json.dumps(raw) and len(raw[0][2]) == 64
    bob = c.post("/api/admin/keys", json={"name": "Bob", "role": "member"}, headers=h).json()
    hb = {"Authorization": f"Bearer {bob['token']}"}
    assert c.get("/api/bots", headers=hb).status_code == 200 and c.get("/api/admin/keys", headers=hb).status_code == 403
    assert c.delete(f"/api/admin/keys/{made['id']}", headers=h).status_code == 409  # last admin
    c.post("/api/admin/keys", json={"name": "Carol", "role": "admin"}, headers=h)
    assert c.delete(f"/api/admin/keys/{bob['id']}", headers=h).status_code == 200
    assert c.get("/api/bots", headers=hb).status_code == 401
    listing = c.get("/api/admin/keys", headers=h).json()
    assert "token" not in json.dumps(listing) and any(k["last_used"] for k in listing["keys"])
    assert c.get("/api/bots", headers={"Authorization": b"Bearer \xc3\xa9-nonascii"}).status_code == 401


def test_env_and_database_keys_coexist(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "root:admin:Root")
    h = {"Authorization": "Bearer root"}
    t = c.post("/api/admin/keys", json={"name": "Dana", "role": "viewer"}, headers=h).json()["token"]
    assert c.get("/api/bots", headers={"Authorization": f"Bearer {t}"}).status_code == 200
    assert c.post("/api/bots/builder/messages", json={"content": "hi"}, headers={"Authorization": f"Bearer {t}"}).status_code == 403  # viewer is read-only


def test_readiness_and_config_validation(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.get("/api/health/ready").json() == {"ready": True, "errors": []}
    monkeypatch.setenv("CFA_ENV", "production")
    r = c.get("/api/health/ready")
    assert r.status_code == 503 and "no access keys are configured" in r.json()["errors"]
    monkeypatch.setenv("CFA_API_KEYS", "k:admin:A")
    monkeypatch.setenv("CFA_SECRET_KEY", "x")
    monkeypatch.setenv("CFA_ALLOW_TMP_DB", "1")
    assert c.get("/api/health/ready").status_code == 200
    assert "max-age" in c.get("/api/health").headers["strict-transport-security"]


def test_request_ids_json_logs_and_no_store(tmp_path, monkeypatch, caplog):
    c = client(tmp_path, monkeypatch)
    with caplog.at_level(logging.INFO, logger="cfa.access"):
        r = c.get("/api/bots", headers={"x-request-id": "trace-abc-123"})
        c.get("/s/secret-share-token")
    assert r.headers["x-request-id"] == "trace-abc-123" and r.headers["cache-control"] == "no-store"
    lines = [json.loads(x.message) for x in caplog.records if x.name == "cfa.access"]
    assert lines[0]["rid"] == "trace-abc-123" and lines[0]["status"] == 200 and "ms" in lines[0]
    assert lines[1]["path"] == "/s/***" and "secret-share-token" not in json.dumps(lines)
    assert "strict-transport-security" not in r.headers


def test_wal_mode_and_online_backup_restore(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert main.connect().execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    c.post("/api/brain/notes", json={"title": "Keep me", "body": "important"})
    b = c.post("/api/admin/backup").json()
    assert b["name"].startswith("cfa-") and b["bytes"] > 0
    assert [x["name"] for x in c.get("/api/admin/backups").json()] == [b["name"]]
    data = c.get(f"/api/admin/backups/{b['name']}").content
    assert data.startswith(b"SQLite format 3")
    restored = tmp_path / "restored.db"
    restored.write_bytes(data)
    assert sqlite3.connect(restored).execute("SELECT COUNT(*) FROM notes WHERE title='Keep me'").fetchone()[0] == 1
    assert c.get("/api/admin/backups/../../etc/passwd").status_code in (404, 422)
    assert c.get("/api/admin/backups/evil.db").status_code == 404


def test_retention_purges_old_data_but_never_the_audit_log(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    c.post("/api/bots/strategist/messages", json={"content": "old question"})
    con = sqlite3.connect(main.DB_PATH)
    con.execute("UPDATE bot_messages SET created_at='2020-01-01T00:00:00+00:00'")
    con.execute("UPDATE agent_activity SET ts='2020-01-01T00:00:00+00:00'")
    con.commit()
    before = c.get("/api/security/audit/verify").json()["checked"]
    r = c.post("/api/admin/retention", json={"days": 30}).json()
    assert r["deleted"]["bot_messages"] >= 2 and r["deleted"]["agent_activity"] >= 1
    assert c.get("/api/bots/strategist/messages").json() == []
    v = c.get("/api/security/audit/verify").json()
    assert v["valid"] and v["checked"] >= before
    assert c.post("/api/admin/retention", json={"days": 1}).status_code == 422


def test_export_has_content_but_no_secrets(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch, "adm:admin:A,mem:member:B")
    h = lambda t: {"Authorization": f"Bearer {t}"}
    c.post("/api/admin/keys", json={"name": "Z", "role": "viewer"}, headers=h("adm"))
    assert c.get("/api/admin/export", headers=h("mem")).status_code == 403
    text = c.get("/api/admin/export", headers=h("adm")).text
    assert "token_hash" not in text and "token_enc" not in text and "cfa_" not in text
    assert json.loads(text)["bots"]
