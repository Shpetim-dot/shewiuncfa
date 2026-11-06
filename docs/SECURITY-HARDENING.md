# Security hardening

Goal: make the running platform expensive to attack, not "unhackable". No web application is
unhackable — the honest promise is: short attack surface, no anonymous admin, no user enumeration,
no leaked internals, and evidence when something happens.

## What is enforced today

| Layer | Control |
|---|---|
| Transport | HSTS in production; cookies `Secure` + `HttpOnly` + `SameSite=Lax` |
| Headers | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, `X-Permitted-Cross-Domain-Policies: none`, `Permissions-Policy`, strict CSP with `frame-ancestors 'none'` |
| API surface | `/docs`, `/redoc`, `/openapi.json` return **404 in production** unless `CFA_PUBLIC_DOCS=1` |
| Authn | Argon2id, Argon2 timing equaliser on unknown accounts (no user enumeration), account lock after N failures, per-IP/per-email throttling, session revocation on password reset and role change |
| Authz | Role hierarchy enforced server-side; every query filtered by `org_id`; viewers read-only |
| CSRF | Double-submit token **plus** `Origin` check for cookie-authenticated unsafe methods |
| Abuse | Durable per-organisation rate limit (`CFA_RATELIMIT`), 1 MB request body cap, 1.5 MB upload cap |
| SSRF | MCP/provider URLs: https only, DNS resolution, private/loopback/link-local blocked, no redirects |
| Secrets | Fernet-encrypted provider/MCP keys, keys never logged, tokens stored only as SHA-256 |
| Evidence | Organisation audit chain + per-agent hash chain, both verifiable and exportable |
| Leakage | Errors return `{"detail": ...}` without stack traces; logs contain request id, path, status, user — never tokens |

## Answers to "can it be reverse engineered / cracked?"

* **Source code**: it is a Python server. Publishing the repo is not a vulnerability; security must
  not depend on hidden code. What protects the business is the data, the accounts and the
  governance logic — all server-side.
* **Frontend**: `app.js` is readable by design (no build step). No secrets, no business rules and
  no API keys live there. Minifying would change nothing security-relevant.
* **Licence cracking**: there is no offline licence check to crack. Plans and limits are enforced
  server-side from the organisation's billing row; a modified client only locks itself out.
* **"Hacking"**: the realistic vectors are stolen credentials, a malicious MCP server, and
  prompt injection into agent memory. Mitigations: Argon2 + lockout + sessions, SSRF guard +
  approval binding for tools, draft/quarantine memory with instruction detection, panic switch,
  audit chains.

## Still open (external, cannot be done from inside the repo)

1. External penetration test and a retest report.
2. Dependency and container scanning in CI (Dependabot/Trivy), secret scanning.
3. WAF / bot protection at the edge and a documented DDoS plan.
4. SSO/SAML + SCIM for enterprise buyers.
5. Incident response runbook rehearsal, status page, security.txt + disclosure policy.
6. Encryption at rest for the volume and key management outside the host.
