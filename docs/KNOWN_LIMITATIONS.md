# Known limitations (honest list)

**Not built yet (exact remaining work)**
1. **Remaining installation-wide state.** Organisations, roles, invitations and row-level tenant
   scoping exist (v9, see `docs/AUTH.md` and `docs/TENANCY.md`). Still shared by all
   organisations on one instance: the rate limiter, backups (`/api/admin/backup*`), the `settings`
   schema flag and the Stripe webhook dedupe table. Backups therefore stay operator-only.
2. **Durable workflow engine, visual builder, scheduler.** Council and research run in-process and do not survive a restart. Needs persistent execution records, a worker with retries/backoff/cancel/resume, budgets per run, then a graph editor.
3. **Real integrations (Slack, Notion, HubSpot).** The catalog entries are demos unless connected through an MCP server; no OAuth adapters yet.
4. **Computer use / browser:** only the provider contract and status endpoint. The research "Reader view" is a text extract, not a browser.
5. **Billing:** existing Stripe code has not been verified in test mode; no usage-based plans.
6. **Performance engine / model comparison, marketplace versioning, SSO/SAML/MFA, GDPR export and
   deletion endpoints.** Password reset, email verification and invitations exist; SSO/SAML and
   MFA do not. A GDPR export exists for workspace data but not for accounts, sessions and audit.
7. **Approvals:** a crash during an external call leaves it `executing`; it is not retried (at most once). No provider-side idempotency key.
8. **Embeddings:** agent chat retrieval is BM25 only; semantic ranking exists in `/api/brain/search`.
9. **Cost totals** are partial until price records exist; the monthly cap counts priced calls only.
10. **SQLite**, single node, in-process rate limiting: fine for a pilot, not for horizontal scale. Plan PostgreSQL before multi-tenant.
11. Provider URLs are checked when added, not on every call (DNS rebinding not covered at call time).

**Production readiness: not yet.** Suitable for a supervised pilot with one customer after: HTTPS reverse proxy, `CFA_SECRET_KEY` set, an owner account created and `CFA_ALLOW_SIGNUP=0` again, SMTP configured, backups scheduled and a restore tested, and a legal review of data processing terms. No compliance claim (GDPR or other) is made.

**Serverless note:** without SQLite FTS5 (some runtimes lack it) the Brain falls back to a plain scan; set `CFA_DISABLE_FTS=1` to force it. On Vercel the database lives in `/tmp` and is lost on cold starts, so it is demo-only there. Use a persistent host (Fly, Render, Docker) for real data.
