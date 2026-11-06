# Shewiun CFA

**CFA — Control & Focus Architecture** is a provider-agnostic workspace for coordinating AI agents, shared knowledge and team-style agent discussions.

> MVP status: working starter application. The Council currently supports a deterministic demo mode; connect an OpenAI-compatible endpoint to enable live model responses.

## Features
- Workspace dashboard with projects, tasks and recent activity
- CFA Brain: source-aware knowledge entries with type, confidence and source
- CFA Council: start a multi-role discussion and receive a synthesis
- CFA Control: inspect agents and their operating status
- CFA Security: deny-by-default policy map, persisted human-approval queue, and SHA-256 hash-linked audit events with integrity verification
- SQLite persistence; responsive dark navy / cream UI
- Backend patterns informed by open-source projects including BoundFlow, oc8, LangGraph, Letta and AgentLens (see docs/backend-reference-architecture.md)
- Optional OpenAI-compatible chat-completions integration

## Run locally
Requires Python 3.11+.

```bash
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Optional live model
Set these in your environment or `.env`:
- `CFA_MODEL_BASE_URL` — OpenAI-compatible API base, default `https://api.openai.com/v1`
- `CFA_MODEL_API_KEY` — API key
- `CFA_MODEL_NAME` — model identifier, default `gpt-4o-mini`

Without a key, Council runs in clearly labeled demo mode. Never commit real keys.

## API
- `GET /api/health`
- `GET/POST /api/projects`
- `GET/POST /api/brain`
- `GET /api/agents`
- `GET/POST /api/council`
- `GET /api/activity`
- `GET /api/security/policies`
- `GET/POST /api/security/approvals`
- `POST /api/security/approvals/{id}/decision`
- `GET /api/security/audit`
- `GET /api/security/audit/verify`

## Tests

Install test dependencies and run the security API tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Security notes
This is an MVP, not a hardened multi-user production system. It does not execute arbitrary tools or shell commands. Before production use, add authentication, per-user authorization, encrypted secret storage, rate limiting, backups, structured provider-specific controls and deployment secrets. Model calls can send the entered meeting prompt to the configured provider.


## Durable Agent Runtime

The runtime adds a persisted SQLite queue for Council jobs, step-by-step checkpoints, run history, cancellation requests, bounded retries, and recovery of interrupted runs on application restart.

### Runtime API

- `POST /api/runtime/runs` — enqueue a Council run (returns HTTP 202)
- `GET /api/runtime/runs` — list recent runs; optional `status` and `limit`
- `GET /api/runtime/runs/{id}` — inspect input, checkpoint state, result, and event timeline
- `POST /api/runtime/runs/{id}/retry` — retry a failed/cancelled run from its last checkpoint
- `POST /api/runtime/runs/{id}/cancel` — request cancellation between agent steps

Run statuses: `queued`, `running`, `completed`, `failed`, `cancelled`.

The worker persists its transcript after each completed speaker. If the process restarts, queued/running runs are recovered and continue from the next checkpoint. This initial implementation intentionally supports one application worker process because SQLite is the queue and state store. Use PostgreSQL plus a lease-based worker queue before horizontal scaling. A model call interrupted before its checkpoint may be repeated, so external side effects must not be added to this loop without idempotency and a controlled tool gateway.

Tests include the security API and the runtime's demo-mode end-to-end flow:

```bash
pip install -r requirements-dev.txt
pytest -q
```
