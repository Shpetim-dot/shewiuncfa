# Multi-tenancy

Status: implemented and tested (`tests/test_tenancy.py`, 9 tests; plus `e2e/tenant-e2e.mjs`,
20 HTTP checks against a running server). One database, row-level isolation.

## Model

Every data table carries `org_id`. The HTTP middleware sets a `ContextVar` (`cfa_core.TENANT`)
from the authenticated principal; `cfa_core.org()` returns it and every query filters on it.

* **Legacy / open dev mode** uses the constant organisation `default`. Existing installations
  therefore keep working without a migration step.
* **First registration** calls `adopt_org()`: all rows of `default` move into the new
  organisation, so an upgrade keeps agents, notes, teams and the audit history.
* **Additional organisations** get their own copy of the four council agents
  (`seed_org_agents`), because agents are organisation-owned, not installation-owned.

## Tables

| Kind | Tables |
|---|---|
| Business data (`org_id` column, scoped queries) | bots, bot_messages, notes, note_versions, note_embeddings, calls, teams, channels, channel_messages, grants, mcp_servers, research, pending_calls, selftests, approvals, audit_events, runtime_runs, runtime_events, llm_usage, model_prices, providers, api_keys, leads, activity, council, brain, projects, agent_activity, brain_events |
| Per-organisation commercial state (composite key) | `org_billing(org_id)`, `org_usage(org_id, period, metric)`, `org_settings(org_id, key)`, `org_apps(org_id, app_id)`, `org_events(org_id, day, name)` |
| Deliberately global | `stripe_events` (webhook dedupe by Stripe event id), `settings` (schema version flag only) |

## Keys that had to be rebuilt

The legacy schema made natural keys globally unique, which makes a second organisation
impossible. `_migrate_org_uniqueness()` rebuilds three tables **once** (guarded by
`settings.schema_v8_org_keys`):

| Table | Before | After |
|---|---|---|
| `bots` | `id` primary key | `PRIMARY KEY(org_id, id)` — two orgs can both have `strategist` |
| `notes` | `title` UNIQUE | `UNIQUE(org_id, title)` |
| `teams` | `name` UNIQUE | `UNIQUE(org_id, name)` |

The rebuild copies rows, recreates triggers (FTS) and re-creates the org index. It runs inside
`apply_tenancy()` and is skipped if the marker row exists.

## Audit chain

Each organisation has its own hash chain: `append_audit` uses the last `event_hash` **of that
organisation** as `previous_hash`, and `/api/security/audit/verify` verifies only the caller's
chain. A tenant can neither read nor break another tenant's chain.

## Background work

* `runtime_worker` executes runs outside a request. `_execute_runtime_run` reads the run's
  `org_id` and sets `TENANT` for the whole run, so notes, council rows, usage and audit events
  land in the right organisation.
* The authorisation self-test calls the app through an in-process ASGI client and forwards the
  caller's cookies, CSRF header and bearer token, so the probes run as the caller in the
  caller's organisation. The internal `x-cfa-internal` header only bypasses the rate limiter.
* `POST /s/{token}` (shared self-test report) is intentionally unscoped: the token itself is the
  capability. It exposes only that report.

## What is still installation-wide

* `GET /api/admin/backup*` snapshots the whole database and is therefore operator-only; in a
  multi-tenant deployment the operator must not hand those files to a customer.
* Rate limiting is in-process (per IP), not per organisation.
* There is no per-organisation data residency or encryption key separation yet.

## Tests

`tests/test_tenancy.py` proves, for two organisations in one database: notes (list, get, verify,
graph, search), agents (list, messages, scopes), calls (+ the drafts they write), approvals
(list, decide), audit (both chains valid, no event overlap, export `org_id` differs), apps
(connect state, grant refusal), teams (same name in both orgs), self-test (isolated), usage
counters, and the legacy-data adoption path.
