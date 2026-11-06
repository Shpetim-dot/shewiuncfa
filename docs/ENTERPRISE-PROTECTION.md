# Enterprise protection — what exists and what a big company does differently

This page is deliberately blunt: it separates what the repository enforces from the
organisational controls that no code can supply.

## Implemented in this codebase

| Control | Where |
|---|---|
| No anonymous admin, fail-closed in production | `app/cfa_core.py` middleware, `tests/test_auth.py` |
| Argon2id, lockout, throttling, timing-equalised login | `app/auth.py` |
| CSRF double submit + Origin check | `app/auth.py`, `tests/test_hardening.py` |
| Per-organisation rate limit, durable | `app/ratelimit.py` |
| Security headers, docs off in production | `app/cfa_core.py` |
| SSRF guard, encrypted provider/MCP keys | `app/mcp_apps.py`, `app/gateway.py` |
| Approval bound to payload hash + TTL + atomic claim | `app/mcp_apps.py` |
| Organisation audit chain + per-agent hash chain | `app/main.py`, `app/agent_audit.py` |
| GDPR org deletion with slug confirmation | `app/admin.py` |
| Emergency snapshot with SHA-256 + audit entry | `POST /api/admin/emergency-backup` |
| Metrics snapshot for monitoring | `GET /api/admin/metrics` |

## How large companies actually defend this class of product

1. **Defence in depth** — CDN/WAF in front, app-level authz, per-tenant isolation, least privilege.
2. **Assume breach** — short-lived credentials, key rotation, break-glass accounts with alerts.
3. **Immutable backups** — 3-2-1 rule, offline/immutable copy, restore drill quarterly, checksums.
4. **Detection** — central log pipeline (SIEM), alert on auth anomalies, decoy endpoints, canaries.
5. **Change safety** — dependency scanning, container scanning, secret scanning, signed artefacts.
6. **People** — on-call, incident commander, tabletop exercises, disclosure policy, pentest + retest.

## What is still missing here (external work, not code)

* WAF/DDoS, SIEM pipeline, alert routing.
* Immutable offsite backup target and a rehearsed restore (the drill is documented, not executed).
* Pentest and retest, dependency/secret scanning in CI.
* SSO/SAML + SCIM, break-glass process, tabletop exercise.
* Honeypot/decoy endpoints were prototyped and **removed again** because the logging path did not
  prove itself green in tests. They are listed as a next step, not as a shipped capability.
