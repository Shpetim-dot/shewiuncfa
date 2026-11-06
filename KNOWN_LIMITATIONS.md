# Known limitations (honest list)

**Not built yet (exact remaining work)**
1. **Organizations, invitations, roles beyond admin/member/viewer, tenant isolation.** The app is single-tenant. Needs an `org_id` on every table, scoped queries, scoped queues/caches/files and cross-tenant tests. Do not host several customers in one instance until this exists.
2. **Durable workflow engine, visual builder, scheduler.** Council and research run in-process and do not survive a restart. Needs persistent execution records, a worker with retries/backoff/cancel/resume, budgets per run, then a graph editor.
3. **Real integrations (Slack, Notion, HubSpot).** The catalog entries are demos unless connected through an MCP server; no OAuth adapters yet.
4. **Computer use / browser:** only the provider contract and status endpoint. The research "Reader view" is a text extract, not a browser.
5. **Billing:** existing Stripe code has not been verified in test mode; no usage-based plans.
6. **Performance engine / model comparison, marketplace versioning, SSO/MFA, GDPR export and deletion endpoints.**
7. **Approvals:** a crash during an external call leaves it `executing`; it is not retried (at most once). No provider-side idempotency key.
8. **Embeddings:** agent chat retrieval is BM25 only; semantic ranking exists in `/api/brain/search`.
9. **Cost totals** are partial until price records exist; the monthly cap counts priced calls only.
10. **SQLite**, single node, in-process rate limiting: fine for a pilot, not for horizontal scale. Plan PostgreSQL before multi-tenant.
11. Provider URLs are checked when added, not on every call (DNS rebinding not covered at call time).

**Production readiness: not yet.** Suitable for a supervised pilot with one customer after: HTTPS reverse proxy, `CFA_SECRET_KEY` set, auth enabled (no open dev mode), backups scheduled and a restore tested, and a legal review of data processing terms. No compliance claim (GDPR or other) is made.

**Serverless note:** without SQLite FTS5 (some runtimes lack it) the Brain falls back to a plain scan; set `CFA_DISABLE_FTS=1` to force it. On Vercel the database lives in `/tmp` and is lost on cold starts, so it is demo-only there. Use a persistent host (Fly, Render, Docker) for real data.
