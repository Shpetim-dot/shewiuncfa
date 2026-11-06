import asyncio, json
from fastapi.testclient import TestClient
from app import main
from app import cfa_core as pf


def test_chair_uses_its_own_model(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "chair.db")
    seen = []

    async def fake_llm(system, user, model=None, ctx=None):
        seen.append((system[:20], model))
        return "Recommendation: x"

    monkeypatch.setenv("CFA_MODEL_API_KEY", "k")
    monkeypatch.setattr(pf, "llm", fake_llm)
    bots = {b: {"name": b, "model": f"model-{b}", "system": b, "spaces": ["shared"], "scopes": []} for b in ("strategist", "skeptic", "chair")}
    item = pf.CallIn(topic="Should we run a pilot?", bot_ids=["strategist", "skeptic"], rounds=1)

    async def run():
        return [e async for e in pf._run_call(item, {"name": "t"}, bots, {"strategist": [], "skeptic": []}, 0)]

    with TestClient(main.app):  # initialises the schema
        asyncio.run(run())
    chair_calls = [m for s, m in seen if s.startswith("chair")]
    assert chair_calls == ["model-chair"]


def test_mixed_mode_is_not_labelled_live(monkeypatch):
    monkeypatch.setenv("CFA_MODEL_API_KEY", "k")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("CFA_HF_TOKEN", raising=False)
    assert pf.model_live("gpt-x") is True
    assert pf.model_live("hf:foo/bar") is False


def test_presets_expose_real_differences(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "presets.db")
    with TestClient(main.app) as c:
        data = {p["id"]: p for p in c.get("/api/presets").json()}
    assert data["freelancer"]["level"] == "Light" and data["freelancer"]["read_only"] == 0
    assert not data["developer"]["can_request_approval"]  # computed from scopes, not hand-written
    assert data["fintech"]["proposes_payments"] and data["fintech"]["read_only"] >= 1
    assert all(p["flow"] for p in data.values())


def test_research_accepts_optional_context(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "research.db")
    monkeypatch.delenv("CFA_MODEL_API_KEY", raising=False)
    with TestClient(main.app) as c:
        r = c.post("/api/research", json={"question": "What do small agencies need?", "depth": "quick", "context": "audience: 5-person agencies"})
        assert r.status_code == 200
        assert c.post("/api/research", json={"question": "What do small agencies need?", "context": "x" * 2001}).status_code == 422
