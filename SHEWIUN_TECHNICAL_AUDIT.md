# Shewiun CFA – Technical Audit (Phase 0, v6 snapshot)

Stack: FastAPI, SQLite (WAL), httpx, Fernet (cryptography), vanilla JS frontend. Single node. Baseline tests: 73 passed.

## Verified findings (against current code)
| # | Finding | Status |
|---|---------|--------|
| 1 | Chair LLM call passed `None` instead of the Chair's configured model (`platform.py::_run_call`) | **Confirmed, fixed**, regression test added |
| 2 | Run-level `mode` was derived from a global key check, not from models actually used; mixed live/demo runs were labelled "live" | **Confirmed, fixed** (`live` / `demo` / `mixed`) |
| 3 | Approved tool-call execution did not re-check grant, suspension or risk class (`mcp_apps.py::execute`) | **Confirmed, fixed** |
| 4 | Duplicate execution race: status check and update were separate (check-then-act) | **Confirmed, fixed** via atomic `pending -> executing` claim |
| 5 | Approval was not bound to payload hash, policy version or expiry | **Fixed** (hash, policy version, TTL, tests incl. tampering) |
| 6 | A crash during an external call leaves the call in `executing`; it is never retried automatically (at most once). No idempotency key is sent to providers | Open, documented |
| 7 | Runtime queue is SQLite + in-process asyncio worker; no tenant/workspace/user IDs, no budgets | Partial, open |
| 8 | No organizations/RBAC beyond admin/key roles; no tenant isolation | Missing |
| 9 | Brain retrieval was substring keyword matching | **Improved**: FTS5/BM25 ranking, permission filter in SQL, optional embeddings (flag) |
| 10 | No provider registry, no usage or cost tracking | **Fixed**: encrypted registry, usage rows from provider token counts, sourced price records, fallbacks, monthly cap |
| 11 | Slack/Notion/HubSpot are catalog/demo entries unless MCP-connected | Demo |

## Capability matrix (code-based, not yet re-verified by e2e tests)
Council: partial · Model Gateway: partial · Brain: partial · Workflows: partial (Council runs only) · MCP: partial · Integrations: demo · Background: partial · Scheduler: missing · Performance engine: missing · Control Center: partial · Multi-tenancy: missing · Billing: partial (Stripe code unverified) · Marketplace: demo · Security: partial.

## Tests after this session
75 passed (73 existing + 2 new). Fix 1 test verified to fail when the fix is reverted.

## Next (priority order)
1. Approval binding (payload hash, expiry, policy version) + idempotency key + `failed_retryable` state.
2. Usage/cost tracking in `llm()` (provider usage metadata, versioned prices).
3. Durable workflow graph (versioned definitions, tenant/workspace IDs, budgets).
4. Org/RBAC/tenant isolation, then real Slack/Notion/HubSpot adapters.

## Changelog v7 (UI slice, Phase A)
- Agent avatars: flat face avatars (hand-built SVG: tile, two-colour ring, eyes/brows/mouth). Core agents have fixed faces, other agents get a stable face and colour pair from their id/name. States: idle blink, thinking (eyes look around, mouth talks, ring turns). Disabled under `prefers-reduced-motion`.
- Presets: cards show level, flow, agent count, read-only agents and approval ability (computed from scopes; only `level` and `flow` are hand-written). Flows are Council discussions started by the user, not background automation.
- Deep research: two inputs (question, optional context), depth/web as chips, new `context` field in `POST /api/research*`. "Reader view" shows the source being read as a text extract and is labelled as not a browser. A real browser view needs an isolated browser provider (not connected).
- Agent creation: icon picker removed (icons no longer drive the avatar).
- Still open: Teams/channels/org, Inventory owner+sponsor, Brain hybrid search, approval binding, cost tracking.
