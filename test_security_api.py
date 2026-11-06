from fastapi.testclient import TestClient

from app import main


def client_for_test(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test-cfa.db")
    return TestClient(main.app)


def test_unknown_action_is_denied_and_audited(tmp_path, monkeypatch):
    with client_for_test(tmp_path, monkeypatch) as client:
        response = client.post("/api/security/approvals", json={
            "action_type": "unknown.dangerous.action",
            "description": "Try an action that is not in the policy map",
            "risk_level": "low",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        audit = client.get("/api/security/audit/verify")
        assert audit.status_code == 200
        assert audit.json()["valid"] is True
        assert audit.json()["checked"] >= 1


def test_high_risk_action_requires_one_human_decision(tmp_path, monkeypatch):
    with client_for_test(tmp_path, monkeypatch) as client:
        created = client.post("/api/security/approvals", json={
            "action_type": "external.write",
            "description": "Send a message to an external system",
            "risk_level": "high",
            "requested_by": "test-agent",
        })
        assert created.status_code == 200
        approval = created.json()
        assert approval["status"] == "pending"

        decision = client.post(
            f"/api/security/approvals/{approval['id']}/decision",
            json={"decision": "approved", "decided_by": "reviewer", "note": "Test approval"},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "approved"

        duplicate = client.post(
            f"/api/security/approvals/{approval['id']}/decision",
            json={"decision": "rejected", "decided_by": "reviewer"},
        )
        assert duplicate.status_code == 409
        assert client.get("/api/security/audit/verify").json()["valid"] is True


def test_secrets_are_denied_even_when_high_risk(tmp_path, monkeypatch):
    with client_for_test(tmp_path, monkeypatch) as client:
        response = client.post("/api/security/approvals", json={
            "action_type": "secrets.read",
            "description": "Read a secret",
            "risk_level": "critical",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
