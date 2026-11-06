# Implementation changelog (v13)

Tests: `python -m pytest -q` -> **171 passed** (160 + 5 GDPR/storage + 6 hardening).

## GDPR deletion and storage limits
- `DELETE /api/org?confirm=<slug>`: owner-only, slug confirmation, deletes every row of the
  organisation (sessions/tokens/users first because of foreign keys), writes a `deletion_log`
  entry outside the deleted tenant. Other organisations are untouched (tested).
- Plan limits gained `storage_mb` (Free 25, Starter 250, Professional 1 000, Enterprise 10 000);
  uploads are refused with 402 before writing when the organisation would exceed it.

## Security hardening (`docs/SECURITY-HARDENING.md`)
- Additional headers: COOP, CORP, `X-Permitted-Cross-Domain-Policies`, `Permissions-Policy`.
- `/docs`, `/redoc`, `/openapi.json` return 404 in production unless `CFA_PUBLIC_DOCS=1`.
- Cookie-authenticated unsafe requests must also pass an `Origin` check (defence in depth
  behind the CSRF token); bearer clients are exempt.
- Login spends the same Argon2 cost on unknown accounts, so timing no longer reveals whether
  an address exists; the response body is identical either way.
- Documented what hardening can and cannot promise (no secrets in the frontend, server-side
  plan enforcement, SSRF/approval binding for tools, audit evidence) and the external items
  that remain (pentest, dependency scanning, WAF, SSO, IR rehearsal).

# Implementation changelog (v12)

Tests: `python -m pytest -q` -> **160 passed** (154 + 6 new in `tests/test_ratelimit.py`).

## Durable rate limiting (`app/ratelimit.py`, new)
- Counters live in SQLite (`rate_limits`), one row per organisation per minute: they survive
  restarts and are shared by all workers of a deployment. The old in-process IP limiter stays as
  a burst guard for auth endpoints.
- Limits follow the plan (Free 120/min, Starter 600, Professional 2 000, Enterprise 10 000);
  self-hosted (`CFA_BILLING` off) uses `CFA_RATELIMIT_DEFAULT` (10 000), `CFA_RATELIMIT=off`
  disables it.
- Over budget: 429 with `Retry-After: 60` and a machine-readable body; other tenants are
  unaffected (tested).
- Stale windows are pruned opportunistically (~twice per hour).

## Operator metrics (`GET /api/admin/metrics`, new)
- Database size, counts of agents/notes/calls/pending approvals/audit and per-agent audit
  entries/tool calls/queued and failed runs/users/LLM calls, plus the current rate-limit window.
- Reads the local database only; nothing is estimated or fetched externally.

## Documentation
- `docs/OPERATIONS.md`: rate limiting, metrics, the backup/restore drill (with a checklist),
  incident procedure, remaining operational gaps.

# Implementation changelog (v11)

Tests: `python -m pytest -q` -> **154 passed** (148 + 6 new in `tests/test_providers.py`).

## Provider architecture (`app/providers.py`, new)
- Three native wire formats behind one call: OpenAI-compatible `/chat/completions`,
  Anthropic `/v1/messages` (`x-api-key`, `anthropic-version`), Gemini
  `/v1beta/models/{model}:generateContent`.
- Model ids select the adapter (`anthropic:`, `claude:`, `gemini:`, `google:`, name patterns,
  registered provider ids, `hf:`); `CFA_MODEL_TIMEOUT` bounds each attempt.
- Usage is normalised to `{tokens_in, tokens_out}` from each provider's own usage block, so cost
  rows and the usage report stay comparable. Honest cost rule unchanged (no price -> NULL).
- `live()` and `/api/health.model_configured` now consider Anthropic and Gemini keys, so a
  deployment with only one native key reports as live instead of "demo".
- Tests use `httpx.MockTransport`: URL, headers, body and token mapping are asserted for all
  three formats plus the 401 -> readable 502 translation. No test touches the network.

## Documentation
- `docs/PROVIDERS.md`: adapters, env vars, resolution order, error/retry policy, how to add one.

# Implementation changelog (v10)

Tests: `python -m pytest -q` -> **148 passed** (137 + 11 new in `tests/test_agent_audit.py`).

## Per-agent audit trail (`app/agent_audit.py`, new)
- One append-only, hash-linked chain per (organisation, agent), `agent_audit` table.
- Entries for messages, replies, tool calls, tool requests, denials and propose-only actions.
- `GET /api/bots/{id}/audit`, `/audit/verify`, `/audit/export` (NDJSON), organisation-scoped.
- Tampering is detectable per agent; a failing audit write never breaks a request.

## Billing: plans, per-organisation subscriptions, revenue (`app/billing.py`, rewritten)
- Four plans: Free, Starter, Professional, Enterprise, with agents, messages, calls, research,
  uploads, MCP servers, **seats**, **API calls** and **activity retention** limits.
  Legacy ids `pro`/`team`/`pilot` are mapped on read.
- Server-side enforcement: messages/calls/research/uploads/API calls counted in `org_usage`;
  seat limit on invitations; retention capped by plan.
- Stripe per organisation: checkout (org in `client_reference_id` + metadata), portal, invoice list,
  cancel/resume, webhook for checkout/subscription/invoice events, ISO period ends,
  grace period on `past_due`, idempotent webhook processing, signature verification unchanged.
- Revenue: `GET /api/org/revenue` (MRR/ARR, seats, status) and `GET /api/admin/revenue`
  (all organisations, super admin only).
- `CFA_API_KEYS` now accepts the full role set (owner, super_admin, security_manager, developer).

## Announcements (`app/announcements.py`, new)
- Notice board for engineering teams: platform-wide (super admin) and per organisation (admin),
  audiences `engineering`/`all`, expiry, plain text only, audited creation.
- `GET/POST /api/announcements`, `DELETE /api/announcements/{id}`.

## Documentation
- `docs/BILLING.md` (plans, env, webhook events, test-mode walkthrough, revenue view).
- `docs/AGENT-AUDIT.md` (model, recorded kinds, endpoints, evidence package).
- `docs/COMPETITORS.md` (deep-research modes, CrewAI/LangGraph/AutoGen, observability players,
  where we win, where we lose, production gap list).

# Implementation changelog (v9)

Tests: `python -m pytest -q` → **137 passed** (128 previous + 9 new in `tests/test_tenancy.py`).
Plus `e2e/tenant-e2e.mjs`: 20 checks with two real organisations against a running uvicorn.

## Multi-tenancy (`docs/TENANCY.md`)
- `org_id` on all 29 business tables plus `org_id` in every INSERT; every SELECT/UPDATE/DELETE is
  filtered with `org_id = cfa_core.org()`. The tenant comes from a `ContextVar` that the HTTP
  middleware sets from the authenticated principal; the legacy workspace is the org `default`.
- New per-organisation tables: `org_billing`, `org_usage`, `org_settings`, `org_apps`,
  `org_events` (replacing the single-row `billing`, global `usage`, global `settings` writes,
  global `apps` and the globally keyed `events`).
- One-time rebuild of `bots` (`PRIMARY KEY(org_id,id)`), `notes` and `teams`
  (`UNIQUE(org_id, …)`) so the same agent id, note title and team name can exist in two
  organisations. Guarded by `settings.schema_v8_org_keys`; FTS triggers are recreated.
- First registration adopts the legacy data (`adopt_org`); every further organisation is seeded
  with its own four council agents (`seed_org_agents`).
- Audit chain is now **per organisation**: `previous_hash` is the organisation's last event, and
  verification only walks the caller's chain. Export, retention, audit listing, approvals,
  brain activity and the summary counters are scoped.
- The runtime worker runs each queued run in the run's organisation (`TENANT` set/reset around
  execution), so background results land in the right tenant. The self-test forwards the
  caller's cookies/CSRF/bearer token into its internal client.
- API keys created through `/api/admin/keys` carry their organisation; key lookups return it.

## Behaviour changes
- `GET /api/admin/export` now exports only the caller's organisation and includes `org_id`.
- `POST /api/admin/retention` deletes only rows of the caller's organisation.
- `/api/summary`, `/api/inventory`, `/api/selftest/latest`, `/api/coverage` are per organisation.

## Known gaps after this round
- Stripe still writes through `org_billing` but has never been exercised against Stripe; the
  plan is read per organisation, the checkout metadata carries the org id.
- Rate limiting, provider keys for the *default* environment, backups and the `settings` table
  remain installation-wide (documented in `docs/TENANCY.md`).
# Implementation changelog (v8)

Tests: `python -m pytest -q` → **128 passed** (99 previous + 29 new in `tests/test_auth.py`).
Every new endpoint below is exercised through the HTTP layer in those tests (cookie, bearer,
CSRF, lockout, tenant scoping), not called as a Python function.

## Accounts, sessions, organisations (`app/auth.py`, new)
- **Argon2id** password hashing (fallback PBKDF2-SHA256 600k if native bindings are missing);
  `/api/health` reports which one is active. Minimum length 10, hashes never logged.
- **Sessions**: 256-bit opaque token stored as SHA-256, delivered as an HttpOnly `SameSite=Lax`
  cookie (`Secure` in production) and accepted as `Authorization: Bearer`. Lifetime
  `CFA_SESSION_DAYS` (14). List and revoke endpoints; a password reset revokes all sessions.
- **CSRF**: cookie-authenticated unsafe requests need `X-CSRF-Token` matching the `cfa_csrf`
  cookie. Bearer clients are exempt. The frontend helper sends it automatically.
- **Brute force**: per-IP and per-email throttling plus an account lock after
  `CFA_AUTH_LOCKOUT_AFTER` failures. Failed counters are committed before the 401 is raised.
- **Endpoints**: `GET /api/auth/status`, `POST /api/auth/register|login|logout`,
  `GET /api/auth/me`, `POST /api/auth/password/forgot|reset`, `POST /api/auth/verify-email`,
  `POST /api/auth/verify-email/resend`, `GET /api/auth/sessions`, `DELETE /api/auth/sessions/{id}`,
  `GET /api/org/members`, `POST /api/org/invitations`, `POST /api/org/invitations/accept`,
  `PATCH/DELETE /api/org/members/{id}`.
- **Roles**: `viewer < developer < security_manager < admin < owner < super_admin`, with legacy
  aliases (`member` = `developer`). Writes require `developer`; admin endpoints require `admin`;
  nobody can grant a role at or above their own; role changes revoke sessions.
- **Fail closed**: as soon as one user exists, anonymous `/api/*` is 401. In `CFA_ENV=production`
  with no identity configured the API answers 503 instead of silently becoming an open admin.
  This removes the open-admin hole that the public Vercel demo had.
- **Organisations**: `orgs`, `users.org_id`, invitations, member management, all scoped in SQL.
  Data tables (agents, notes, calls, approvals, audit, usage, billing) are **not** org-scoped yet;
  one organisation per instance until the next round (documented in `docs/AUTH.md`,
  `docs/KNOWN_LIMITATIONS.md`).

## Mail (`app/mail.py`, new)
- stdlib `smtplib` sender configured by `SMTP_*`. Without configuration nothing is sent, one
  warning is logged **without the message body** (bodies contain single-use tokens), and
  `/api/health` reports `mail_configured: false`. `CFA_DEV_TOKENS=1` returns tokens directly
  in development only.

## UI (`app/static/app.js`)
- Login view now uses email + password; on a fresh installation it switches to a
  "create your workspace" form driven by `/api/auth/status` (no more manual token box).
- `api()`/`stream()`/`streamGet()` send `credentials: 'same-origin'` and the CSRF header.
- The account panel shows organisation, email and role; "Sign out" calls `POST /api/auth/logout`.

## Health
- `/api/health` reports `auth_mode` (`session`/`keys`/`open`), `password_hash` and
  `mail_configured`; the duplicated `version` key was removed (single source: `cfa_core.VERSION`).
- Readiness adds "no user account exists" next to the legacy "no access keys are configured".

## Dependencies
- `requirements.txt`: added `argon2-cffi`.

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
