"""Agent Launch Review: deterministic readiness rules (no LLM).

A structured self-assessment based on the user's answers. It is NOT a security test,
audit or certification and does not verify any real system.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent if (_HERE.parent / "static").is_dir() else _HERE
PLAYBOOK_PATH = Path(__file__).resolve().parent / "playbooks" / "agent-launch.v1.json"
PLAYBOOK_VERSION = 1
DISCLAIMER = (
    "This is a self-assessment based on what you entered. It is not a security test, audit or "
    "certification, and it does not verify your system."
)
Tri = Literal["yes", "no", "unknown"]
Severity = Literal["critical", "high", "medium", "low"]
Action = Literal["payments", "refunds", "account_changes", "data_export", "customer_messages", "infra_changes", "none"]
Untrusted = Literal["emails", "web", "tickets", "documents", "tool_outputs", "none"]
IRREVERSIBLE = {"payments", "refunds", "account_changes", "infra_changes"}
FINANCIAL = {"payments", "refunds"}
ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SECRET = re.compile(
    r"(sk-[a-z0-9_-]{16,}|AKIA[0-9A-Z]{12,}|eyJ[a-zA-Z0-9_-]{20,}\.|-----BEGIN [A-Z ]*PRIVATE KEY|api[_-]?key\s*[:=]\s*\S{8,})",
    re.IGNORECASE,
)


class Answers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    environment: Literal["pilot", "production"] | None = None
    purpose: str | None = Field(default=None, max_length=500)
    actions: list[Action] | None = Field(default=None, max_length=7)
    write_access: Tri | None = Field(default=None, alias="writeAccess")
    approval: Literal["none", "above_threshold", "always", "unknown"] | None = None
    amount_limits: Tri | None = Field(default=None, alias="amountLimits")
    identity: Literal["agent_own", "shared_service_account", "user_credentials", "unknown"] | None = None
    kill_switch: Tri | None = Field(default=None, alias="killSwitch")
    audit_log: Tri | None = Field(default=None, alias="auditLog")
    monitoring: Tri | None = None
    incident_owner: Tri | None = Field(default=None, alias="incidentOwner")
    untrusted_inputs: list[Untrusted] | None = Field(default=None, alias="untrustedInputs", max_length=6)
    injection_mitigations: Tri | None = Field(default=None, alias="injectionMitigations")
    tool_chaining: Tri | None = Field(default=None, alias="toolChaining")

    @field_validator("purpose")
    @classmethod
    def no_secrets(cls, v: str | None) -> str | None:
        if v and SECRET.search(v):
            raise ValueError("purpose looks like it contains a key or token; remove it")
        return v


def _lacking(v: str | None) -> bool:
    return v in (None, "no", "unknown")


def _finding(a: Answers, rid: str, severity: Severity, title: str, why: str, fix: str, fields: list[str]) -> dict[str, Any]:
    unknown = any(getattr(a, f) in (None, "unknown") for f in fields)
    return {"id": rid, "severity": severity, "title": title, "why": why, "fix": fix,
            "basis": "unknown" if unknown else "answered", "triggered_by": fields}


def _has_write(a: Answers) -> bool:
    # Unanswered or unknown write access counts as write access (conservative).
    return a.write_access != "no" or any(x != "none" for x in (a.actions or []))


def _untrusted(a: Answers) -> bool:
    return any(x != "none" for x in (a.untrusted_inputs or []))


def evaluate(a: Answers) -> dict[str, Any]:
    acts = set(a.actions or [])
    out: list[dict[str, Any] | None] = []

    out.append(_finding(a, "R01", "critical", "Money can move without human approval",
        "A wrong or manipulated decision becomes an irreversible financial action.",
        "Require human approval for every payment or refund, or above a low threshold with a hard cap.",
        ["actions", "approval"]) if acts & FINANCIAL and a.approval in (None, "none", "unknown") else None)
    out.append(_finding(a, "R02", "high", "No hard limits on amounts or volume",
        "Without limits one failure can repeat or scale before anyone notices.",
        "Enforce per-action and per-day limits outside the agent, in the payment layer.",
        ["actions", "amount_limits"]) if acts & FINANCIAL and _lacking(a.amount_limits) else None)
    if a.identity == "user_credentials":
        out.append(_finding(a, "R03", "high", "Agent acts with the user's own credentials",
            "The agent inherits every permission the user has, including ones the task never needs.",
            "Give the agent its own identity with least-privilege scopes per tool.", ["identity"]))
    elif a.identity in (None, "unknown", "shared_service_account"):
        out.append(_finding(a, "R03", "medium", "Agent identity is shared or unclear",
            "Actions cannot be attributed or scoped per agent and use case.",
            "Use a dedicated identity per agent with scoped permissions.", ["identity"]))
    w = _has_write(a)
    out.append(_finding(a, "R04", "high", "No fast way to stop the agent",
        "If behavior goes wrong you cannot contain it in minutes.",
        "Add a kill switch that revokes tool access immediately and test it.",
        ["write_access", "kill_switch"]) if w and _lacking(a.kill_switch) else None)
    out.append(_finding(a, "R05", "critical" if acts & IRREVERSIBLE else "high",
        "Untrusted content can steer an agent that can act",
        "Text in emails, pages or tool outputs can carry instructions the agent may follow (prompt injection).",
        "Separate untrusted content from instructions, and gate write tools behind checks the content cannot influence.",
        ["untrusted_inputs", "injection_mitigations"]) if w and _untrusted(a) and _lacking(a.injection_mitigations) else None)
    out.append(_finding(a, "R06", "high", "Agent actions are not fully logged",
        "You cannot reconstruct what happened or prove it to a regulator or customer.",
        "Log every action with agent identity, input, tool call, result and approver.",
        ["write_access", "audit_log"]) if w and _lacking(a.audit_log) else None)
    out.append(_finding(a, "R07", "medium", "No alerts on unusual behavior",
        "Problems are found by customers instead of by you.",
        "Alert on unusual volume, amounts, new tools and rejected approvals.",
        ["write_access", "monitoring"]) if w and _lacking(a.monitoring) else None)
    out.append(_finding(a, "R08", "medium", "Chained tools can combine permissions",
        "Each step may be allowed, yet the combination can reach an action nobody authorized.",
        "Define the allowed action boundary for the whole workflow and test it by trying to cross it.",
        ["tool_chaining", "actions", "approval"]) if a.tool_chaining != "no" and acts & IRREVERSIBLE and a.approval != "always" else None)
    out.append(_finding(a, "R09", "low", "No accountable owner for incidents",
        "Response is slow when nobody owns the decision to stop or roll back.",
        "Name one owner and a backup, and write down the escalation path.",
        ["incident_owner"]) if w and _lacking(a.incident_owner) else None)

    findings = sorted((f for f in out if f), key=lambda f: (ORDER[f["severity"]], f["id"]))
    critical = sum(f["severity"] == "critical" for f in findings)
    high = sum(f["severity"] == "high" for f in findings)
    production = a.environment != "pilot"  # unknown environment is treated as production
    if (critical and production) or critical >= 2:
        verdict = "no-go"
    elif critical == 1 or high:
        verdict = "conditional-go"
    else:
        verdict = "go"
    conditions = [f["fix"] for f in findings if ORDER[f["severity"]] <= 1]
    return {"verdict": verdict, "findings": findings, "conditions": conditions,
            "disclaimer": DISCLAIMER, "playbook_version": PLAYBOOK_VERSION}


router = APIRouter()


@router.get("/api/playbooks/agent-launch")
def playbook() -> dict[str, Any]:
    return json.loads(PLAYBOOK_PATH.read_text(encoding="utf-8"))


@router.post("/api/reviews/agent-launch")
def review(answers: Answers) -> dict[str, Any]:
    # Phase 1: stateless. Answers are evaluated and not stored.
    return evaluate(answers)


@router.get("/review/agent-launch")
def page() -> FileResponse:
    return FileResponse(ROOT / "static" / "agent-launch.html")
