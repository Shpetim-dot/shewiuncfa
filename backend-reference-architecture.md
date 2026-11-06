# CFA backend reference architecture

CFA should borrow proven architectural patterns, not copy another project's implementation wholesale. The goal is to keep the core provider-neutral, inspectable, and small enough to evolve.

## Reference projects reviewed

- **BoundFlow** — https://github.com/boundflow/boundflow  
  Useful patterns: separate control plane from execution workers, durable workflow state, approval gates, runtime budgets, and audit decisions distinct from execution traces.
- **oc8** — https://github.com/oc8-ai/oc8  
  Useful patterns: provider-neutral model routing, scoped knowledge, a single controlled gateway for tools, and self-hosted deployment.
- **LangGraph** — https://github.com/langchain-ai/langgraph  
  Useful patterns: checkpointed state, resumable runs, explicit workflow steps, and persistence across interruptions.
- **Letta** — https://github.com/letta-ai/letta  
  Useful patterns: persistent agent state and memory managed as a first-class resource rather than buried in prompts.
- **AgentLens** — https://github.com/agentkitai/agentlens  
  Useful patterns: queryable run history, event timelines, and tamper-evident audit chains.

These projects overlap with many CFA ideas. CFA's product challenge is to make their relevant patterns work together behind one simple workspace and consistent permission model—not to claim the individual features are unprecedented.

## Current MVP implementation

- FastAPI REST API with SQLite persistence.
- Durable Council runtime queue with persisted run states, per-speaker checkpoints, event timeline, bounded retries, cancellation requests, and restart recovery.
- Provider-neutral Council adapter using an OpenAI-compatible chat-completions endpoint, with clearly labeled demo mode.
- CFA Brain entries retain source, type, confidence and creation time.
- Policy reference endpoint with explicit allow, approval_required, and deny outcomes. Unknown action types default to deny.
- Approval requests persist in SQLite and are single-decision: a second decision returns a conflict.
- Audit events are SHA-256 hash-linked and the API can verify the chain.
- Security UI displays the approval queue and exposes a manual audit integrity check.
- No external tools, shell commands, or consequential actions are executed by the approval endpoint. Approval records a decision only.

## Important limitations

The hash chain detects accidental or unsophisticated modification, but it is not a signed external ledger. A database administrator who can rewrite the whole database can recompute the chain. Production hardening should add an external witness or signed checkpoints.

The current policy map is a reference implementation, not a complete policy engine. Authentication and authorization are not yet implemented, so the app must not be exposed publicly with sensitive data. The current SQLite schema is suitable for a local MVP, not concurrent multi-tenant production workloads. The runtime worker is deliberately single-process; horizontal scaling requires a PostgreSQL-backed queue with leases/heartbeats and concurrency-safe claiming.

## Suggested next architecture steps

1. Extract provider adapters, policy evaluation, audit storage and workflow orchestration into separate modules.
2. Introduce typed agent/run/task records and persisted run states: queued, running, waiting_approval, completed, failed, cancelled.
3. Add checkpoints and idempotent retry semantics before enabling long-running agent work.
4. Add authentication, workspace-level authorization, rate limits and secure secret management before public deployment.
5. Move production persistence to PostgreSQL; add migrations and integration tests.
6. Route every future tool call through one gateway that checks policy, scopes credentials, requires approval where needed, and records an audit event.
7. Add provider-specific adapters behind a shared interface; never assume all vendors support identical tool-calling or structured-output behavior.

## Validation

Run local tests with:

    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    pytest -q
