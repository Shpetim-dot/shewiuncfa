import time

from fastapi.testclient import TestClient

from app import main


def test_runtime_council_run_is_durable_and_completes(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "runtime-test.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)

    with TestClient(main.app) as client:
        created = client.post("/api/runtime/runs", json={
            "topic": "Choose the next CFA backend milestone",
            "roles": ["Strategist", "Skeptic", "Builder"],
            "rounds": 1,
        })
        assert created.status_code == 202
        run_id = created.json()["id"]

        deadline = time.time() + 5
        run = None
        while time.time() < deadline:
            response = client.get(f"/api/runtime/runs/{run_id}")
            assert response.status_code == 200
            run = response.json()
            if run["status"] in {"completed", "failed", "cancelled"}:
                break
            time.sleep(0.05)

        assert run is not None
        assert run["status"] == "completed", run
        assert run["state"]["next_index"] == 4
        assert run["result"]["mode"] == "demo"
        assert len(run["result"]["transcript"]) == 4
        assert any(event["event_type"] == "run.completed" for event in run["events"])

        history = client.get("/api/runtime/runs")
        assert history.status_code == 200
        assert any(item["id"] == run_id for item in history.json())
