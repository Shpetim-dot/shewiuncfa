import itertools

import pytest
from fastapi.testclient import TestClient

from app import main
from app.agent_launch import Answers, evaluate

STRONG = dict(environment="production", actions=["customer_messages"], writeAccess="yes", approval="always",
              amountLimits="yes", identity="agent_own", killSwitch="yes", auditLog="yes", monitoring="yes",
              incidentOwner="yes", untrustedInputs=["emails"], injectionMitigations="yes", toolChaining="no")
RISKY = dict(environment="production", actions=["payments", "refunds"], writeAccess="yes", approval="none",
             amountLimits="no", identity="user_credentials", killSwitch="no", auditLog="no", monitoring="no",
             incidentOwner="no", untrustedInputs=["emails", "tool_outputs"], injectionMitigations="no", toolChaining="yes")


def ev(**over):
    return evaluate(Answers(**{**STRONG, **over}))


def ids(res):
    return {f["id"] for f in res["findings"]}


def test_strong_agent_gets_go_without_critical_or_high():
    res = ev()
    assert res["verdict"] == "go"
    assert not any(f["severity"] in ("critical", "high") for f in res["findings"])


def test_risky_payments_agent_in_production_is_no_go():
    res = evaluate(Answers(**RISKY))
    assert res["verdict"] == "no-go"
    assert {"R01", "R02", "R03", "R04", "R05", "R06"} <= ids(res)


def test_payments_without_approval_is_critical():
    f = next(f for f in ev(actions=["payments"], approval="none")["findings"] if f["id"] == "R01")
    assert f["severity"] == "critical"


def test_single_critical_in_pilot_is_conditional_go_with_conditions():
    res = ev(environment="pilot", actions=["payments"], approval="none")
    assert res["verdict"] == "conditional-go" and res["conditions"]


def test_unknown_answer_is_flagged_as_assumed():
    f = next(f for f in ev(killSwitch="unknown")["findings"] if f["id"] == "R04")
    assert f["basis"] == "unknown"


def test_untrusted_input_with_irreversible_action_is_critical():
    f = next(f for f in ev(actions=["account_changes"], injectionMitigations="no")["findings"] if f["id"] == "R05")
    assert f["severity"] == "critical"


def test_never_unconditional_go_when_critical_exists():
    for approval, inj, env in itertools.product(
            ["none", "above_threshold", "always", "unknown"], ["yes", "no", "unknown"], ["pilot", "production"]):
        res = ev(environment=env, actions=["payments"], approval=approval, injectionMitigations=inj)
        if any(f["severity"] == "critical" for f in res["findings"]):
            assert res["verdict"] != "go"


def test_empty_answers_are_not_go():
    assert evaluate(Answers())["verdict"] != "go"


def test_findings_sorted_by_severity():
    order = ["critical", "high", "medium", "low"]
    s = [order.index(f["severity"]) for f in evaluate(Answers(**RISKY))["findings"]]
    assert s == sorted(s)


def test_api_roundtrip_and_disclaimer():
    client = TestClient(main.app)
    r = client.post("/api/reviews/agent-launch", json=RISKY)
    assert r.status_code == 200 and r.json()["verdict"] == "no-go"
    assert "not a security test" in r.json()["disclaimer"]


@pytest.mark.parametrize("payload", [
    {**STRONG, "purpose": "use key sk-abcdefghijklmnopqrstuvwx for billing"},
    {**STRONG, "approval": "sometimes"},
    {**STRONG, "unexpected": 1},
])
def test_api_rejects_secrets_bad_values_and_unknown_fields(payload):
    assert TestClient(main.app).post("/api/reviews/agent-launch", json=payload).status_code == 422


def test_playbook_and_page_are_served():
    client = TestClient(main.app)
    assert client.get("/api/playbooks/agent-launch").json()["id"] == "agent-launch"
    assert "Agent launch review" in client.get("/review/agent-launch").text
