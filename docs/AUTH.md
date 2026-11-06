# Authentication, sessions and roles

Status: implemented in `app/auth.py`, covered by `tests/test_auth.py` (29 tests).
Everything below is enforced on the server; the browser UI only reflects it.

## How a request becomes a principal

The single place that decides this is `cfa_core._handle` → `auth.resolve()`.

Accepted credentials, in order:

1. `cfa_session` cookie (HttpOnly, `SameSite=Lax`, `Secure` when `CFA_ENV=production`)
2. `Authorization: Bearer <session-token>`
3. `Authorization: <legacy-api-key>` or `Authorization: Bearer <legacy-api-key>` —
   `CFA_API_KEYS` and hashed keys created under `/api/admin/keys` keep working

The resulting principal looks like:

```json
{"name": "owner@example.com", "role": "owner", "user_id": "…", "org_id": "…",
 "org_name": "Acme", "via": "cookie", "open": false}
```

## Fail-closed rules

| Situation | Behaviour |
|---|---|
| No user, no API key, `CFA_ENV` unset | Open dev mode (local development, existing tests) |
| No user, no API key, `CFA_ENV=production` | Every `/api/*` call returns **503**; `/api/health` explains why |
| At least one user exists | Anonymous `/api/*` returns **401** (public endpoints excepted) |

Public endpoints: `/api/health`, `/api/public`, `/api/auth/status`, `/api/auth/login`,
`/api/auth/register` (bootstrap only), `/api/auth/password/forgot`,
`/api/auth/password/reset`, `/api/auth/verify-email`, `/api/org/invitations/accept`,
`/api/playbooks/*`, `/api/reviews/*`, `POST /api/leads`, `POST /api/events`,
`POST /api/billing/webhook`.

## Roles

| Role | Rank | Typical use |
|---|---|---|
| `viewer` | 1 | Read-only: dashboard, audit, reports |
| `developer` | 2 | Build and run agents, write memory, run calls |
| `security_manager` | 3 | Review approvals and policies (read + decide) |
| `admin` | 4 | Manage members, keys, providers, billing |
| `owner` | 5 | Created with the organisation; cannot be removed |
| `super_admin` | 6 | Operator of the installation (cross-organisation, later rounds) |

`member` and `anon` are legacy aliases (`member` = `developer`, `anon` = no rights) so that
old `CFA_API_KEYS` deployments keep working.

Rules that are enforced in code:

* Any write method (anything but GET/HEAD/OPTIONS) requires rank ≥ `developer`.
* `need_admin()` requires rank ≥ `admin`; a role change revokes that user's sessions.
* Nobody can grant a role at or above their own (except `super_admin`).
* The `owner` cannot be removed and only the `owner`/`super_admin` may change that role.

## Passwords

* **Argon2id**, `time_cost=2`, `memory_cost=65536`, `parallelism=2`, 32-byte hash.
* Fallback to PBKDF2-SHA256 (600 000 iterations) if the native bindings are missing;
  `/api/health` reports which one is active (`password_hash`).
* Minimum 10 characters. Hashes are never logged and never leave the database.
* Failed logins increment a counter; after `CFA_AUTH_LOCKOUT_AFTER` (default 8) the account
  is locked for 15 minutes. Login attempts are additionally limited per IP and per email
  (`CFA_AUTH_ATTEMPTS`, default 10/minute).

## Sessions

* 256-bit opaque token, stored as SHA-256 only (the database never holds a usable token).
* Lifetime `CFA_SESSION_DAYS` (default 14), sliding `last_seen`, revocable per session.
* `GET /api/auth/sessions` lists them, `DELETE /api/auth/sessions/{id}` revokes one.
* Password reset revokes **all** sessions of that user.

## CSRF

Cookie-authenticated unsafe requests must send `X-CSRF-Token` equal to the `cfa_csrf`
cookie (double submit, `SameSite=Lax` as the second line of defence). Bearer requests are
exempt because they are not sent automatically by a browser. The frontend helper
`authHeaders()` in `app/static/app.js` adds the header.

## Organisations

`orgs` + `users.org_id` are the tenant anchor. This round implemented:

* first organisation + owner on bootstrap (`POST /api/auth/register`)
* invitations (`POST /api/org/invitations` → `POST /api/org/invitations/accept`)
* member list scoped to the caller's organisation (`GET /api/org/members`)
* role changes and removal, both scoped by `org_id` in the SQL predicate

Not yet scoped by organisation (next round): agents, notes, calls, approvals, audit
events, usage and billing. Until that lands, **run one organisation per instance**;
`docs/KNOWN_LIMITATIONS.md` says so explicitly.

## Email

Transactional mail goes through `app/mail.py` (stdlib `smtplib`). Configure `SMTP_*`.
Without SMTP nothing is sent, `/api/health` reports `mail_configured: false`, and
`CFA_DEV_TOKENS=1` makes the API return the single-use token directly (development only).

## Operations checklist for a new deployment

1. `CFA_ENV=production`, `CFA_SECRET_KEY=<fernet key>`, `CFA_DATABASE_PATH` on a volume.
2. `CFA_ALLOW_SIGNUP=1` for the first start, create the owner account in the browser.
3. Set `CFA_ALLOW_SIGNUP=0` and restart. From now on only invitations create users.
4. Configure `SMTP_*`, otherwise invitations and password resets cannot be delivered.
5. Optional: `CFA_REQUIRE_EMAIL_VERIFICATION=1` once mail delivery works.
