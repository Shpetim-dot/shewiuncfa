# Operations

## Rate limiting (durable, per organisation)

`app/ratelimit.py` counts requests in SQLite (`rate_limits`), one row per organisation per minute.
It survives restarts and multi-worker deployments, unlike the in-process IP limiter.

| Plan | Requests per minute |
|---|---|
| Free | 120 |
| Starter | 600 |
| Professional | 2 000 |
| Enterprise | 10 000 |

* `CFA_RATELIMIT=off` disables it (development).
* With `CFA_BILLING` off (self-hosted) the limit is `CFA_RATELIMIT_DEFAULT` (10 000) so a local
  install is never throttled by accident.
* Over budget: `429` with `Retry-After: 60` and
  `{"detail":{"code":"rate_limited","limit":…,"window_seconds":60,"message":…}}`.
* Windows older than five minutes are pruned opportunistically.

## Metrics

`GET /api/admin/metrics` (admin) returns, for the caller's organisation:

* `database_bytes` / `database_mb`
* counts: agents, notes, calls, pending approvals, audit events, per-agent audit entries,
  tool calls, queued/failed runtime runs, users, LLM calls
* the current `rate_limit` window (used/limit)

It reads only the local database — no external calls, no invented numbers. Ship it to your
monitoring with a small scraper; the JSON is stable.

## Backup and restore drill

Backups use SQLite's online backup API (`POST /api/admin/backup`), so they are consistent while
the app keeps writing. Files live next to the database in `backups/`, `CFA_BACKUP_KEEP` is
honoured (default 14).

Drill (run once per quarter, document the date and result):

1. `POST /api/admin/backup` → note the file name.
2. `GET /api/admin/backups/{name}` → download.
3. On a scratch host: `CFA_DATABASE_PATH=/tmp/drill.db uvicorn app.main:app`
   with the downloaded file copied to `/tmp/drill.db`.
4. `GET /api/health/ready` → `{"ready": true}`; open the workspace and check agents, notes and
   `/api/security/audit` integrity.
5. Record: backup size, restore duration, first failing check if any.

A backup that has never been restored is a hypothesis, not a backup.

## Incident basics

1. Suspend everything: `POST /api/security/panic {"action":"suspend_all","reason":"…"}`.
2. Preserve evidence: `GET /api/security/audit/export` and `GET /api/bots/{id}/audit/export`.
3. Rotate `CFA_SECRET_KEY` only together with re-entering provider/MCP keys (tokens are encrypted
   with it), and revoke sessions/keys that may be affected.
4. Announce it in-app: `POST /api/announcements` with `level: "critical"`.

## Known operational gaps

* No metrics/trace exporter (Prometheus/OTLP) yet, only the JSON snapshot.
* Backups are instance-wide; in multi-tenant operation the operator must not hand them out.
* No automated restore test in CI (the drill above is manual).
* Log aggregation is whatever the host provides (stdout JSON lines from `cfa.access`).
