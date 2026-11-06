# SaaS roadmap — status against the master brief

Legend: ✅ done and tested · 🟡 partial · ⬜ not started

Last updated with the tenancy round. Test suite: **137 passed** + 20 HTTP checks in `e2e/tenant-e2e.mjs`.

## 3. Authentication and user management

| Item | Status | Where |
|---|---|---|
| Registration (first org + owner) | ✅ | `POST /api/auth/register`, `app/auth.py` |
| Login / logout | ✅ | `POST /api/auth/login`, `/api/auth/logout` |
| Argon2id password hashing | ✅ | `hash_password`, PBKDF2 fallback, reported in `/api/health` |
| Password reset | ✅ | `/api/auth/password/forgot|reset`, single-use tokens, revokes all sessions |
| Email verification | ✅ | `/api/auth/verify-email`, `/resend`, optional enforcement |
| Session management | ✅ | HttpOnly `SameSite=Lax` cookie, bearer accepted, list + revoke |
| Secure cookie configuration | ✅ | `Secure` in production, HttpOnly session, readable CSRF cookie |
| Session expiry and revocation | ✅ | `CFA_SESSION_DAYS`, revoke on logout / role change / password reset |
| Brute-force protection | ✅ | per-IP and per-email throttling, 15-minute account lock |
| Rate limiting | ✅ | durable per-organisation limiter in SQLite, plan-based (`docs/OPERATIONS.md`) |
| Roles: super admin, owner, admin, security manager, developer, viewer | ✅ | `ROLE_RANK` in `app/auth.py`, legacy `member`/`admin`/`viewer` aliases |
| Auth enabled by default in production | ✅ | 503 without identity, 401 for anonymous once a user exists |

## 4. Multi-tenancy

| Item | Status | Where |
|---|---|---|
| Organisations | ✅ | `orgs` table, `users.org_id`, `POST /api/auth/register` |
| Users inside organisations | ✅ | `users`, `GET /api/org/members` |
| Invitations | ✅ | `POST /api/org/invitations`, `/accept`, 7-day single-use tokens |
| Team management (members, roles, removal) | ✅ | `PATCH/DELETE /api/org/members/{id}` |
| Workspace management | ✅ | one workspace per organisation, row-level scoping (`docs/TENANCY.md`) |
| Org-scoped API keys | ✅ | keys carry `org_id`, lookups return it |
| Org-scoped agents / policies / audit / cost | ✅ | agents, memory, calls, teams, channels, approvals, audit, usage, providers, prices, research, apps |
| Tenant isolation tests | ✅ | `tests/test_tenancy.py` (9) + two-org HTTP e2e |
| GDPR deletion | ✅ | `DELETE /api/org` with slug confirmation + `deletion_log` |
| Storage metering | ✅ | plan `storage_mb`, checked before upload |

## 5. Billing and Stripe

| Item | Status | Where |
|---|---|---|
| Plans free / starter / professional / enterprise | ✅ | `app/billing.py`, legacy ids mapped |
| Stripe checkout, portal, webhooks, signature | ✅ code | per org; **test-mode walkthrough still outstanding** (`docs/BILLING.md`) |
| Per-organisation Stripe customer | ✅ | `org_billing.customer_id`, one per organisation |
| Plan changes, cancellations, renewals, payment failures | 🟡 | webhook handlers written, untested end to end |
| Grace period, invoices, usage metering, upgrade/downgrade, cancel/resume | ✅ | grace days, `/invoices`, `org_usage`, checkout-based plan change, `/cancel` `/resume` |
| No real payments during tests | ✅ | no live keys in the repo; tests mock the HTTP transport |

## 6. Usage and cost control

| Item | Status | Where |
|---|---|---|
| API calls, agent runs, tokens, model cost, MCP calls, storage | 🟡 | API calls, messages, calls, research, uploads, seats metered; tokens/cost in `llm_usage`; storage still missing |
| Monthly overview, budget limits, warnings | 🟡 | `/api/usage`, monthly cap (`CFA` budget), no warning notifications |
| Costs only when calculable | ✅ | `cost` stays `NULL` without a price record, report says "partial" |
| Per-organisation cost | ⬜ | |

## 7. Models and providers

| Item | Status | Where |
|---|---|---|
| OpenAI, Anthropic, Gemini, Mistral, OpenAI-compatible | ✅ | native Anthropic + Gemini adapters, OpenAI-compatible for the rest (`docs/PROVIDERS.md`) |
| Provider registry, encrypted keys | ✅ | `app/gateway.py`, Fernet via `CFA_SECRET_KEY` |
| Model selection, timeouts, retries, rate limits, error surface | ✅ | `cfa_core.llm`, 3 attempts with backoff, translated errors |

## Next rounds (in order)

1. ~~Tenant data scoping~~ — done in this round (`docs/TENANCY.md`).
2. **Stripe per organisation** — one customer per org, checkout with `client_reference_id=org_id`, webhook updates `orgs`, plan limits read from `orgs.plan`, test-mode walkthrough documented.
3. **Usage per organisation** — meter API calls, agent runs, MCP calls and storage; surface in the UI; enforce limits server-side.
4. **Production hardening** — ~~durable rate limiting~~ done; open: Postgres option, restore drill execution, metrics exporter, GDPR deletion.
5. **Product depth** — research upgrades R1-R7 from `docs/COMPETITORS.md` (iterative re-planning, claim-to-source binding, contradiction section), eval harness, agent-to-agent message signing.
