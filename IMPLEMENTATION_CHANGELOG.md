# Implementation changelog (v7)

Tests: `python -m pytest -q` → **99 passed** (73 original, 26 new). New tests were checked to fail when the feature is removed (mutation check on payload binding and the Chair model).

## Security and governance
- **Approval binding** (`mcp_apps.py`): each external write stores `payload_hash` (bot, app, tool, exact args), `policy_version` (grant set and risk class) and `expires_at` (`CFA_APPROVAL_TTL_MINUTES`, default 1440). Execution refuses and audits: changed payload, expired approval, changed permissions, suspended agent, revoked grant, disconnected app, pre-binding legacy approvals.
- **No double execution**: atomic `pending → executing` claim; a second request gets 409.
- Chair uses its own model; run mode is `live`, `demo` or `mixed` from the models actually used.

## Multi-model gateway (`gateway.py`)
- Provider registry: any OpenAI-compatible provider, key encrypted with `CFA_SECRET_KEY`, never returned or logged, SSRF-checked URL, connection test. Models are addressed as `provider-id:model`.
- Usage: every model call (chat, council, research, channel, embedding, test) records provider, model, requested model, tokens from the provider's own usage data, latency, status, error text.
- Cost: only from price records (`PUT /api/prices`, a source is required). No price → cost is `unknown` and the report says it is partial.
- Fallback models: used only after provider failures (402/429/502), each use recorded. Missing key never triggers a fallback.
- Monthly budget cap: calls stop with 402 once priced spend reaches the cap.

## Brain (`brain.py`)
- SQLite FTS5 index kept in sync by triggers; BM25 ranking, title weighted; space and status filters applied in SQL before ranking; notes flagged as instruction-like stay out until reviewed.
- `GET /api/brain/search` (as human or as a specific agent, enforcing its spaces and `memory.read`), `POST /api/brain/reindex`.
- Semantic search is a feature flag (`CFA_EMBEDDING_MODEL`). The response says `keyword` or `hybrid` truthfully; if the embedding provider fails it falls back to keyword and says so. Agent retrieval during chats uses BM25 only.

## Teams, inventory
- Team channels (`channels.py`): `#general` per team, more channels, messages. Agents answer only when @mentioned, only if active, only from notes in their spaces, each reply labelled live/demo/error.
- Inventory: owner, sponsor, purpose, last activity, accountability gaps, summary endpoint, admin-only editing with audit.

## Computer use (`computer_use.py`)
- Provider interface, required guarantees, approval-required action list, feature flag. **No provider is bundled; status is `unconfigured` and sessions are refused (501).**

## UI
- Face avatars, preset explanations, two-box research with reader view (earlier slice); new Models & usage view; channels in Teams; owner/sponsor/purpose in Inventory; payload hash and expiry shown on tool calls.

## Environment variables (new)
`CFA_SECRET_KEY` (required for provider keys and stored MCP tokens), `CFA_APPROVAL_TTL_MINUTES`, `CFA_EMBEDDING_MODEL`, `CFA_COMPUTER_USE`, `CFA_COMPUTER_USE_PROVIDER`.

## Migrations
Additive only, applied at startup: tables `providers`, `model_prices`, `llm_usage`, `channels`, `channel_messages`, `note_embeddings`, FTS table `notes_fts` with triggers (backfilled); columns `pending_calls.payload_hash/expires_at/policy_version`, `bots.sponsor/purpose`. Nothing is dropped. Back up first with the existing admin backup endpoint.
