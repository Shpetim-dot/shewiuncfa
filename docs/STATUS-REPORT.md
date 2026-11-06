# Status report — Shewiun CFA after the SaaS rounds

Verified: `python -m pytest -q` → **171 passed**, 0 failed. 165 routes. 8 commits.
Everything below is either a test in `tests/` or a documented external step.

## Master brief → status

| § | Requirement | Status | Evidence |
|---|---|---|---|
| 3 | Auth: register, login, logout, Argon2id, reset, verification, sessions, cookies, expiry, brute force, rate limit, roles | ✅ | `tests/test_auth.py` (29), `docs/AUTH.md` |
| 3 | Auth on by default in production, no anonymous admin | ✅ | 401 anonymous / 503 without identity, `test_auth.py` |
| 4 | Organisations, users, invitations, teams, roles, org-scoped keys/agents/policies/audit/cost, tenant tests | ✅ | `tests/test_tenancy.py` (9) + two-org HTTP e2e (20 checks), `docs/TENANCY.md` |
| 5 | Plans Free/Starter/Professional/Enterprise, checkout, portal, webhooks, signature, plan change, cancel, renewal, payment failure, grace, invoices, metering, limits, upgrade/downgrade | ✅ code / ⚠️ live unverified | `tests/test_sell.py` + `tests/test_agent_audit.py` (revenue), `docs/BILLING.md` walkthrough |
| 5 | Customer per organisation, idempotent webhooks, server-side entitlement, no real payments in tests | ✅ | `org_billing`, `stripe_events`, mocks only |
| 6 | Usage: API calls, messages, runs, tokens, cost, MCP, storage, monthly, per org, budget, warnings, limits | ✅ except budget alerts | `app/billing.py`, `app/gateway.py`, `org_usage` |
| 6 | Cost only when calculable, unknown stays unknown | ✅ | `gateway.record_usage`, `/api/usage` |
| 7 | Providers: OpenAI, Anthropic, Gemini, Mistral, compatible; encrypted keys; model selection; timeouts; retries; rate limits; errors | ✅ | `app/providers.py`, `tests/test_providers.py` (6), `docs/PROVIDERS.md` |
| — | Per-agent audit trail (requested later) | ✅ | `app/agent_audit.py`, `tests/test_agent_audit.py` (6), `docs/AGENT-AUDIT.md` |
| — | Revenue per organisation (requested later) | ✅ | `/api/org/revenue`, `/api/admin/revenue` |
| — | Announcements for engineering teams | ✅ | `app/announcements.py` |
| — | Production hardening: rate limits, headers, docs off, GDPR, storage, metrics | ✅ | `tests/test_ratelimit.py` (6), `tests/test_gdpr.py` (5), `tests/test_hardening.py` (6), `docs/OPERATIONS.md`, `docs/SECURITY-HARDENING.md` |

## Still open — all outside the repository

1. **Stripe test-mode walkthrough** (8 steps, `docs/BILLING.md`): needs a Stripe account and price ids.
   Code is complete; this is the only functional item I cannot verify from here.
2. External penetration test, dependency/container scanning, secret scanning in CI.
3. Postgres migration + horizontal worker, metrics exporter (Prometheus/OTLP).
4. SSO/SAML + SCIM, WAF/DDoS plan, status page, IR rehearsal.
5. Research depth upgrades R1–R7 from `docs/COMPETITORS.md`.

## Honest verdict

This is a **multi-tenant SaaS MVP with production-grade security primitives**, not a finished
production product: billing is code-complete but not proven against Stripe, there is no pentest,
no SSO, and the database is still single-node SQLite. For a supervised pilot with one to five
customers it is ready once item 1 is done.
