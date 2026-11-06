"""Computer-use provider abstraction (browser, terminal, files).

Nothing here runs agent commands. Agent-generated actions must never execute on the application server, so the only supported path is an isolated
provider (a separate sandbox or a hosted browser service) that implements ComputerUseProvider. No provider is bundled: until one is registered the
feature is reported as unconfigured and every session request is refused. This file defines the contract and the policy so a provider can be plugged in.
"""
from __future__ import annotations

import os
from typing import Any, Protocol

from fastapi import APIRouter, HTTPException, Request

from app import cfa_core as pf

router = APIRouter()

# Rules every provider must satisfy before it is allowed to serve a session (checked by `ready_problems`).
REQUIRED_GUARANTEES = ["isolated per workspace", "no host filesystem or environment access", "network egress limited to an allowlist",
                       "cpu, memory, disk and time limits", "secrets never exposed to the model", "full action recording", "human takeover for MFA, CAPTCHA and sensitive steps"]
APPROVAL_REQUIRED = ["send email or message", "change customer data", "purchase or payment", "publish content", "change access rights", "delete data"]


class ComputerUseProvider(Protocol):
    name: str

    def guarantees(self) -> list[str]: ...
    async def open_session(self, workspace: str, allowed_domains: list[str], ttl_seconds: int) -> dict[str, Any]: ...
    async def act(self, session_id: str, action: dict[str, Any]) -> dict[str, Any]: ...
    async def close_session(self, session_id: str) -> None: ...


PROVIDERS: dict[str, ComputerUseProvider] = {}  # filled by a deployment, never by user input


def enabled() -> bool:
    return os.getenv("CFA_COMPUTER_USE") == "1"


def ready_problems() -> list[str]:
    name = os.getenv("CFA_COMPUTER_USE_PROVIDER", "")
    if not enabled():
        return ["feature flag CFA_COMPUTER_USE is not set to 1"]
    p = PROVIDERS.get(name)
    if not p:
        return [f"no provider named '{name}' is registered"]
    return [f"provider does not guarantee: {g}" for g in REQUIRED_GUARANTEES if g not in p.guarantees()]


@router.get("/api/computer-use/status")
def status() -> dict[str, Any]:
    problems = ready_problems()
    return {"status": "ready" if not problems else "unconfigured", "problems": problems, "required_guarantees": REQUIRED_GUARANTEES,
            "approval_required_for": APPROVAL_REQUIRED,
            "note": "Agent actions never run on the application server. Browser and terminal use needs an isolated provider; none is connected."}


@router.post("/api/computer-use/sessions")
def open_session(request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    problems = ready_problems()
    if problems:
        raise HTTPException(501, "computer use is not available: " + "; ".join(problems))
    raise HTTPException(501, "session handling is provided by the connected provider")
