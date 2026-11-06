# CFA backend roadmap

## Now — MVP
- [x] Persistent workspace, Brain, Council history and activity
- [x] Optional OpenAI-compatible model integration
- [x] Explicit policy outcomes and persisted approval queue
- [x] Hash-linked audit events and integrity verification
- [x] Basic tests for deny-by-default and single-decision approvals

## Next — reliable agent runtime
- [ ] Extract API routes, provider adapters, policy, audit and persistence into modules
- [x] Add persistent Council runs, per-speaker checkpoints, bounded retries, cancellation requests and restart recovery (single-process SQLite MVP)
- [ ] Move runtime queue to PostgreSQL/lease-based workers for multi-process scaling
- [x] Add cancellation requests and bounded retries for Council runs
- [ ] Add per-step timeouts and idempotency keys before external side effects
- [ ] Record model name, token usage, latency, errors and per-run budget
- [ ] Add streaming Council events to the frontend

## Before public deployment
- [ ] Authentication and workspace/role authorization
- [ ] CSRF/CORS/security-header configuration and rate limits
- [ ] PostgreSQL, schema migrations, backups and restore drills
- [ ] Secret manager integration; redact secrets and sensitive prompt content from logs
- [ ] Tool gateway with sandboxed workers and server-enforced approval checks
- [ ] CI for lint, unit tests, integration tests and dependency/security scanning
- [ ] External signed audit checkpoints and retention controls

## Product principles
1. The model proposes; deterministic backend policy decides.
2. Unknown actions are denied.
3. Approval applies to an exact, reviewable action—not a vague instruction.
4. No agent can bypass the tool gateway.
5. Every run is inspectable, resumable and attributable.
6. Shared knowledge stores provenance and version history.
