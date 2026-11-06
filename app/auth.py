"""Authentication, sessions, roles and organisations.

This is the only place that turns an HTTP request into a principal. Everything else
consumes `request.state.principal`.

Design notes
------------
* Passwords: Argon2id (argon2-cffi). If the native bindings are unavailable the
  module falls back to PBKDF2-SHA256 with 600k iterations and says so in /api/health.
* Sessions: opaque 256-bit token, stored as SHA-256, transport is an HttpOnly
  SameSite=Lax cookie. `Authorization: Bearer <session-token>` is accepted as well,
  so CLI and API clients work without cookies.
* CSRF: cookie-authenticated unsafe requests must send `X-CSRF-Token` matching the
  `cfa_csrf` cookie (double submit). Bearer requests are exempt by construction.
* Fail closed: as soon as one user exists, unauthenticated requests to /api/* are
  rejected. A fresh installation may only bootstrap the first organisation.
* Legacy: `CFA_API_KEYS=token:role:name` and hashed keys from /api/admin/keys keep
  working. They are marked `via="key"` and never get a cookie.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()

# ---------- roles ----------
ROLE_RANK = {"viewer": 1, "developer": 2, "security_manager": 3, "admin": 4, "owner": 5, "super_admin": 6}
ROLES = tuple(ROLE_RANK)
# Backwards compatibility: CFA_API_KEYS still uses admin/member/viewer.
LEGACY_RANK = {"member": ROLE_RANK["developer"], "anon": 0}
WRITE_MIN_RANK = ROLE_RANK["developer"]

SESSION_COOKIE = "cfa_session"
CSRF_COOKIE = "cfa_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,200}\.[A-Za-z]{2,}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
PASSWORD_MIN = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS orgs (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
  plan TEXT NOT NULL DEFAULT 'free', status TEXT NOT NULL DEFAULT 'active',
  stripe_customer_id TEXT, stripe_subscription_id TEXT, subscription_status TEXT,
  current_period_end TEXT, seat_limit INTEGER, limits_json TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY, org_id TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT 'developer',
  password_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
  email_verified_at TEXT, failed_logins INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT, last_login_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(org_id) REFERENCES orgs(id)
);
CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_seen TEXT NOT NULL,
  ip TEXT NOT NULL DEFAULT '', user_agent TEXT NOT NULL DEFAULT '', revoked INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS auth_tokens (
  id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL, used_at TEXT, created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS invitations (
  id TEXT PRIMARY KEY, org_id TEXT NOT NULL, email TEXT NOT NULL COLLATE NOCASE, role TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE, invited_by TEXT NOT NULL, expires_at TEXT NOT NULL,
  accepted_at TEXT, created_at TEXT NOT NULL, UNIQUE(org_id, email)
);
"""

_ensured: set[str] = set()


# ---------- helpers ----------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _in(days: float = 0, minutes: float = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days, minutes=minutes)).isoformat()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _norm_email(email: str) -> str:
    e = (email or "").strip().lower()
    if not EMAIL.match(e):
        raise HTTPException(422, "please enter a valid email address")
    return e


def rank(role: str | None) -> int:
    r = role or ""
    return ROLE_RANK.get(r, LEGACY_RANK.get(r, 0))


def is_production() -> bool:
    return os.getenv("CFA_ENV") == "production"


def db():
    """Same connection factory as the rest of the app, plus the auth schema."""
    con = pf.db()
    key = str(pf._m().DB_PATH)
    if key not in _ensured:
        con.executescript(SCHEMA)
        con.commit()
        _ensured.add(key)
    return con


def user_count() -> int:
    with db() as con:
        return con.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def auth_required() -> bool:
    """True once this installation has any identity configured."""
    return bool(user_count()) or pf.auth_enabled()


# ---------- passwords ----------
def _hasher():
    try:
        from argon2 import PasswordHasher, Type
        return PasswordHasher(time_cost=int(os.getenv("CFA_ARGON2_TIME_COST", "2")),
                              memory_cost=int(os.getenv("CFA_ARGON2_MEMORY_COST", "65536")),
                              parallelism=int(os.getenv("CFA_ARGON2_PARALLELISM", "2")),
                              hash_len=32, salt_len=16, type=Type.ID)
    except Exception:
        return None


_HASHER = _hasher()


def hash_password(password: str) -> str:
    if not password or len(password) < PASSWORD_MIN:
        raise HTTPException(422, f"password must be at least {PASSWORD_MIN} characters")
    if len(password) > 512:
        raise HTTPException(422, "password is too long")
    if _HASHER is not None:
        return _HASHER.hash(password)
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return "pbkdf2_sha256$600000$" + salt.hex() + "$" + dk.hex()


def verify_password(stored: str, password: str) -> bool:
    if not stored or not password:
        return False
    if stored.startswith("$argon2"):
        if _HASHER is None:
            return False
        try:
            return _HASHER.verify(stored, password)
        except Exception:
            return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt_hex, want = stored.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
            return hmac.compare_digest(dk.hex(), want)
        except (ValueError, TypeError):
            return False
    return False


def hash_algorithm() -> str:
    return "argon2id" if _HASHER is not None else "pbkdf2-sha256"


# ---------- principals ----------
def _principal(user_row, via: str, org_row=None) -> dict[str, Any]:
    return {"name": user_row["email"], "role": user_row["role"], "user_id": user_row["id"],
            "org_id": user_row["org_id"], "org_name": org_row["name"] if org_row else "",
            "via": via, "open": False, "email": user_row["email"], "display": user_row["name"] or user_row["email"]}


def _session_principal(token: str, request: Request) -> dict[str, Any] | None:
    if not token:
        return None
    with db() as con:
        row = con.execute(
            "SELECT s.id AS sid, s.expires_at, s.revoked, u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ?", (_hash(token),)).fetchone()
        if not row or row["revoked"] or row["expires_at"] < _now() or row["status"] != "active":
            return None
        org = con.execute("SELECT * FROM orgs WHERE id=?", (row["org_id"],)).fetchone()
        con.execute("UPDATE sessions SET last_seen=? WHERE id=?", (_now(), row["sid"]))
    p = _principal(row, "cookie" if request.cookies.get(SESSION_COOKIE) == token else "bearer", org)
    p["session_id"] = row["sid"]
    return p


def resolve(request: Request) -> dict[str, Any] | None:
    """Session cookie, then bearer session token, then legacy API key. None if anonymous."""
    cookie = request.cookies.get(SESSION_COOKIE, "")
    if cookie:
        p = _session_principal(cookie, request)
        if p:
            return p
    header = request.headers.get("authorization", "")
    token = header[7:].strip() if header.lower().startswith("bearer ") else header.strip()
    if token:
        p = _session_principal(token, request)
        if p:
            return p
        legacy = pf._lookup(token)
        if legacy:
            return {"name": legacy["name"], "role": legacy["role"], "user_id": None,
                    "org_id": legacy.get("org_id"), "org_name": "", "via": "key", "open": False,
                    "email": "", "display": legacy["name"]}
    return None


def origin_ok(request: Request, principal: dict[str, Any]) -> bool:
    """Cookie-authenticated writes must come from our own origin (defence in depth behind CSRF)."""
    if request.method in SAFE_METHODS or principal.get("via") != "cookie":
        return True
    origin = request.headers.get("origin") or ""
    if not origin:
        return True  # same-origin fetches and CLI clients may omit it; CSRF still applies
    allowed = {str(request.base_url).rstrip("/"), (os.getenv("APP_URL") or "").rstrip("/")}
    return any(a and origin.rstrip("/") == a for a in allowed)


def _dummy_hash() -> str:
    """A real Argon2 hash used to spend the same time on unknown accounts."""
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password("timing-equaliser-" + "x" * 24)
    return _DUMMY


_DUMMY: str | None = None


def csrf_ok(request: Request, principal: dict[str, Any]) -> bool:
    if request.method in SAFE_METHODS:
        return True
    if principal.get("via") != "cookie":
        return True
    sent = request.headers.get(CSRF_HEADER, "")
    want = request.cookies.get(CSRF_COOKIE, "")
    return bool(sent and want and hmac.compare_digest(sent, want))


def need(request: Request, *roles: str) -> dict[str, Any]:
    """Require a principal with one of the given roles (or higher)."""
    p = pf._principal(request)
    if not any(rank(p.get("role")) >= rank(r) for r in roles):
        raise HTTPException(403, "insufficient role")
    return p


def need_write(request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    if rank(p.get("role")) < WRITE_MIN_RANK:
        raise HTTPException(403, "your role is read-only")
    return p


# ---------- rate limiting (per IP + identity, in process) ----------
_attempts: dict[str, list[float]] = {}


def _throttle(key: str, limit: int, window: int = 60) -> None:
    now = time.monotonic()
    bucket = [t for t in _attempts.get(key, []) if now - t < window]
    if len(bucket) >= limit:
        _attempts[key] = bucket
        raise HTTPException(429, "too many attempts, try again later")
    bucket.append(now)
    _attempts[key] = bucket


def reset_throttle() -> None:
    _attempts.clear()


def _client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0].strip()


# ---------- session issuance ----------
def _set_cookies(response: Response, token: str, csrf: str, max_age: int) -> None:
    secure = is_production()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure, path="/", max_age=max_age)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, samesite="lax", secure=secure, path="/", max_age=max_age)


def _create_session(con, user_id: str, request: Request) -> tuple[str, str]:
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
    days = float(os.getenv("CFA_SESSION_DAYS", "14"))
    con.execute("INSERT INTO sessions (id,user_id,token_hash,created_at,expires_at,last_seen,ip,user_agent) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), user_id, _hash(token), _now(), _in(days=days), _now(),
                 _client_ip(request), request.headers.get("user-agent", "")[:300]))
    return token, csrf


def _public_user(row) -> dict[str, Any]:
    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"],
            "org_id": row["org_id"], "status": row["status"], "email_verified": bool(row["email_verified_at"]),
            "created_at": row["created_at"]}


def _audit(event: str, actor: str, payload: dict[str, Any]) -> None:
    try:
        pf._m().append_audit(event, actor, payload)
    except Exception:  # auditing must never break authentication
        pass


def _audit_in_org(org_id: str | None, event: str, actor: str, payload: dict[str, Any]) -> None:
    """Authentication happens before a principal exists, so the tenant is set explicitly here."""
    token = pf.TENANT.set(org_id or pf.DEFAULT_ORG)
    try:
        _audit(event, actor, payload)
    finally:
        pf.TENANT.reset(token)


# ---------- payload models ----------
class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=512)
    name: str = Field(default="", max_length=80)
    org_name: str = Field(default="", max_length=80)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=512)


class ForgotIn(BaseModel):
    email: str = Field(max_length=254)


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=512)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class InviteIn(BaseModel):
    email: str = Field(max_length=254)
    role: str = Field(default="developer", max_length=20)


class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(max_length=512)
    name: str = Field(default="", max_length=80)


class RoleIn(BaseModel):
    role: str = Field(max_length=20)


# ---------- status ----------
@router.get("/api/auth/status")
def status() -> dict[str, Any]:
    """Public: tells the UI whether to show login, setup or the open demo workspace."""
    users = user_count()
    return {"auth_required": auth_required(), "setup_required": users == 0 and not pf.auth_enabled(),
            "users": users, "hash": hash_algorithm(), "signup_open": os.getenv("CFA_ALLOW_SIGNUP") == "1",
            "verification_required": os.getenv("CFA_REQUIRE_EMAIL_VERIFICATION") == "1",
            "dev_tokens": os.getenv("CFA_DEV_TOKENS") == "1"}


@router.post("/api/auth/register", status_code=201)
def register(item: RegisterIn, request: Request, response: Response) -> dict[str, Any]:
    """Create the first organisation and its owner.

    After the first user exists this endpoint is closed unless CFA_ALLOW_SIGNUP=1,
    because in this architecture an organisation is provisioned, not self-served.
    """
    email = _norm_email(item.email)
    _throttle("register:" + _client_ip(request), limit=int(os.getenv("CFA_AUTH_ATTEMPTS", "10")))
    with db() as con:
        existing = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing and os.getenv("CFA_ALLOW_SIGNUP") != "1":
            raise HTTPException(403, "sign-up is closed; ask an admin for an invitation")
        if con.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            raise HTTPException(409, "an account with this email already exists")
        org_name = (item.org_name or item.name or email.split("@")[0]).strip()[:80]
        base = re.sub(r"[^a-z0-9]+", "-", org_name.lower()).strip("-")[:32] or "org"
        slug, n = base, 1
        while con.execute("SELECT 1 FROM orgs WHERE slug=?", (slug,)).fetchone():
            n += 1
            slug = f"{base}-{n}"
        org_id, user_id, ts = str(uuid4()), str(uuid4()), _now()
        con.execute("INSERT INTO orgs (id,name,slug,created_at,updated_at) VALUES (?,?,?,?,?)", (org_id, org_name, slug, ts, ts))
        con.execute("INSERT INTO users (id,org_id,email,name,role,password_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (user_id, org_id, email, item.name.strip()[:80], "owner", hash_password(item.password), ts, ts))
        token, csrf = _create_session(con, user_id, request)
        if existing == 0:
            # First organisation takes over the legacy single-workspace data, so an upgrade
            # keeps the agents, notes and audit history that were already there.
            pf.adopt_org(con, org_id)
        if not con.execute("SELECT 1 FROM bots WHERE org_id=?", (org_id,)).fetchone():
            pf.seed_org_agents(con, org_id)  # every organisation gets its own council agents
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        org = con.execute("SELECT * FROM orgs WHERE id=?", (org_id,)).fetchone()
    _set_cookies(response, token, csrf, max_age=int(float(os.getenv("CFA_SESSION_DAYS", "14")) * 86400))
    _audit_in_org(org_id, "org.created", email, {"org_id": org_id, "slug": slug})
    _audit_in_org(org_id, "auth.registered", email, {"user_id": user_id, "role": "owner"})
    return {"user": _public_user(row), "org": {"id": org["id"], "name": org["name"], "slug": org["slug"], "plan": org["plan"]},
            "token": token, "csrf": csrf}


@router.post("/api/auth/login")
def login(item: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    email = (item.email or "").strip().lower()
    ip = _client_ip(request)
    _throttle("login:" + ip, limit=int(os.getenv("CFA_AUTH_ATTEMPTS", "10")))
    _throttle("login:" + email, limit=int(os.getenv("CFA_AUTH_ATTEMPTS", "10")))
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            verify_password(_dummy_hash(), item.password)  # same cost as a real check: no user enumeration by timing
        if not row or not verify_password(row["password_hash"], item.password):
            if row:
                fails = int(row["failed_logins"] or 0) + 1
                lock = _in(minutes=15) if fails >= int(os.getenv("CFA_AUTH_LOCKOUT_AFTER", "8")) else None
                con.execute("UPDATE users SET failed_logins=?, locked_until=?, updated_at=? WHERE id=?",
                            (fails, lock, _now(), row["id"]))
                con.commit()  # the exception below would otherwise roll the counter back
            _audit_in_org(row["org_id"] if row else None, "auth.login_failed", email or "unknown", {"ip": ip})
            raise HTTPException(401, "email or password is incorrect")
        if row["status"] != "active":
            raise HTTPException(403, "this account is " + row["status"])
        if row["locked_until"] and row["locked_until"] > _now():
            raise HTTPException(429, "too many failed attempts, this account is temporarily locked")
        if os.getenv("CFA_REQUIRE_EMAIL_VERIFICATION") == "1" and not row["email_verified_at"]:
            raise HTTPException(403, "please verify your email address first")
        con.execute("UPDATE users SET failed_logins=0, locked_until=NULL, last_login_at=?, updated_at=? WHERE id=?",
                    (_now(), _now(), row["id"]))
        token, csrf = _create_session(con, row["id"], request)
        org = con.execute("SELECT * FROM orgs WHERE id=?", (row["org_id"],)).fetchone()
    _set_cookies(response, token, csrf, max_age=int(float(os.getenv("CFA_SESSION_DAYS", "14")) * 86400))
    _audit_in_org(row["org_id"], "auth.login", email, {"ip": ip, "org_id": row["org_id"]})
    return {"user": _public_user(row), "org": {"id": org["id"], "name": org["name"], "slug": org["slug"], "plan": org["plan"]},
            "token": token, "csrf": csrf}


@router.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    p = pf._principal(request)
    sid = p.get("session_id")
    if sid:
        with db() as con:
            con.execute("UPDATE sessions SET revoked=1 WHERE id=?", (sid,))
        _audit("auth.logout", p.get("name", ""), {"session": sid})
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/api/auth/me")
def me(request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    if not p.get("user_id"):
        return {"user": None, "role": p.get("role"), "via": p.get("via"), "open": bool(p.get("open"))}
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (p["user_id"],)).fetchone()
        org = con.execute("SELECT * FROM orgs WHERE id=?", (p["org_id"],)).fetchone() if p.get("org_id") else None
    if not row:
        raise HTTPException(401, "session is no longer valid")
    return {"user": _public_user(row), "role": row["role"],
            "org": {"id": org["id"], "name": org["name"], "slug": org["slug"], "plan": org["plan"]} if org else None,
            "via": p.get("via"), "open": False}


# ---------- password reset / email verification ----------
def _issue_token(con, user_id: str, kind: str, minutes: int = 60) -> str:
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO auth_tokens (id,user_id,kind,token_hash,expires_at,created_at) VALUES (?,?,?,?,?,?)",
                (str(uuid4()), user_id, kind, _hash(token), _in(minutes=minutes), _now()))
    return token


def _dev_token(token: str) -> dict[str, str]:
    """Tokens are only echoed when the operator opted in (no mailer configured)."""
    return {"token": token} if os.getenv("CFA_DEV_TOKENS") == "1" else {}


@router.post("/api/auth/password/forgot")
def forgot(item: ForgotIn, request: Request) -> dict[str, Any]:
    email = (item.email or "").strip().lower()
    _throttle("forgot:" + _client_ip(request), limit=5, window=300)
    token = ""
    with db() as con:
        row = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if row:
            token = _issue_token(con, row["id"], "reset_password", minutes=30)
    if token:
        from app import mail
        mail.send(email, "Reset your Shewiun password",
                  f"Use this link within 30 minutes: /?reset={token}")
    # Always the same answer: no account enumeration.
    return {"ok": True, **_dev_token(token)}


@router.post("/api/auth/password/reset")
def reset_password(item: ResetIn, request: Request) -> dict[str, Any]:
    _throttle("reset:" + _client_ip(request), limit=10, window=300)
    with db() as con:
        row = con.execute("SELECT * FROM auth_tokens WHERE token_hash=? AND kind='reset_password' AND used_at IS NULL",
                          (_hash(item.token),)).fetchone()
        if not row or row["expires_at"] < _now():
            raise HTTPException(400, "this reset link is invalid or has expired")
        con.execute("UPDATE auth_tokens SET used_at=? WHERE id=?", (_now(), row["id"]))
        con.execute("UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL, updated_at=? WHERE id=?",
                    (hash_password(item.password), _now(), row["user_id"]))
        con.execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (row["user_id"],))  # log out everywhere
    with db() as con:
        target = con.execute("SELECT org_id FROM users WHERE id=?", (row["user_id"],)).fetchone()
    _audit_in_org(target["org_id"] if target else None, "auth.password_reset", "self-service", {"user_id": row["user_id"]})
    return {"ok": True}


@router.post("/api/auth/verify-email")
def verify_email(item: TokenIn) -> dict[str, bool]:
    with db() as con:
        row = con.execute("SELECT * FROM auth_tokens WHERE token_hash=? AND kind='verify_email' AND used_at IS NULL",
                          (_hash(item.token),)).fetchone()
        if not row or row["expires_at"] < _now():
            raise HTTPException(400, "this verification link is invalid or has expired")
        con.execute("UPDATE auth_tokens SET used_at=? WHERE id=?", (_now(), row["id"]))
        con.execute("UPDATE users SET email_verified_at=?, updated_at=? WHERE id=?", (_now(), _now(), row["user_id"]))
    return {"ok": True}


@router.post("/api/auth/verify-email/resend")
def resend_verification(request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    if not p.get("user_id"):
        raise HTTPException(401, "authentication required")
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (p["user_id"],)).fetchone()
        if row["email_verified_at"]:
            return {"ok": True, "already": True}
        token = _issue_token(con, row["id"], "verify_email", minutes=1440)
    from app import mail
    mail.send(row["email"], "Verify your Shewiun email", f"Confirm within 24 hours: /?verify={token}")
    return {"ok": True, **_dev_token(token)}


# ---------- sessions ----------
@router.get("/api/auth/sessions")
def list_sessions(request: Request) -> list[dict[str, Any]]:
    p = pf._principal(request)
    if not p.get("user_id"):
        raise HTTPException(401, "authentication required")
    with db() as con:
        rows = con.execute("SELECT id,created_at,last_seen,expires_at,ip,user_agent FROM sessions "
                           "WHERE user_id=? AND revoked=0 AND expires_at>? ORDER BY last_seen DESC",
                           (p["user_id"], _now())).fetchall()
    return [{**dict(r), "current": r["id"] == p.get("session_id")} for r in rows]


@router.delete("/api/auth/sessions/{session_id}")
def revoke_session(session_id: str, request: Request) -> dict[str, bool]:
    p = pf._principal(request)
    if not p.get("user_id"):
        raise HTTPException(401, "authentication required")
    with db() as con:
        changed = con.execute("UPDATE sessions SET revoked=1 WHERE id=? AND user_id=?", (session_id, p["user_id"])).rowcount
    if not changed:
        raise HTTPException(404, "session not found")
    return {"ok": True}


# ---------- organisation members ----------
@router.get("/api/org/members")
def members(request: Request) -> dict[str, Any]:
    p = pf._principal(request)
    if not p.get("org_id"):
        raise HTTPException(401, "authentication required")
    with db() as con:
        rows = con.execute("SELECT * FROM users WHERE org_id=? ORDER BY created_at", (p["org_id"],)).fetchall()
        invites = con.execute("SELECT id,email,role,expires_at,created_at FROM invitations WHERE org_id=? AND accepted_at IS NULL",
                              (p["org_id"],)).fetchall()
    return {"members": [_public_user(r) for r in rows], "invitations": [dict(i) for i in invites]}


@router.post("/api/org/invitations", status_code=201)
def invite(item: InviteIn, request: Request) -> dict[str, Any]:
    p = need(request, "admin")
    if not p.get("org_id"):
        raise HTTPException(400, "invitations need an organisation")
    email = _norm_email(item.email)
    if item.role not in ROLES or item.role == "super_admin":
        raise HTTPException(422, "unknown role")
    if rank(item.role) >= rank(p["role"]) and p["role"] != "super_admin":
        raise HTTPException(403, "you cannot invite a role at or above your own")
    from app import billing
    billing.check_count("seats", billing.member_count_org(p["org_id"]), 1)
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE email=? AND org_id=?", (email, p["org_id"])).fetchone():
            raise HTTPException(409, "this person is already a member")
        con.execute("DELETE FROM invitations WHERE org_id=? AND email=?", (p["org_id"], email))
        token = secrets.token_urlsafe(32)
        con.execute("INSERT INTO invitations (id,org_id,email,role,token_hash,invited_by,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (str(uuid4()), p["org_id"], email, item.role, _hash(token), p["user_id"] or p["name"], _in(days=7), _now()))
    from app import mail
    mail.send(email, "You are invited to Shewiun", f"Accept within 7 days: /?invite={token}")
    _audit("org.invited", p["name"], {"email": email, "role": item.role})
    return {"ok": True, "email": email, "role": item.role, "expires_in_days": 7, **_dev_token(token)}


@router.post("/api/org/invitations/accept", status_code=201)
def accept_invitation(item: AcceptInviteIn, request: Request, response: Response) -> dict[str, Any]:
    with db() as con:
        inv = con.execute("SELECT * FROM invitations WHERE token_hash=? AND accepted_at IS NULL", (_hash(item.token),)).fetchone()
        if not inv or inv["expires_at"] < _now():
            raise HTTPException(400, "this invitation is invalid or has expired")
        if con.execute("SELECT 1 FROM users WHERE email=?", (inv["email"],)).fetchone():
            raise HTTPException(409, "an account with this email already exists")
        user_id, ts = str(uuid4()), _now()
        con.execute("INSERT INTO users (id,org_id,email,name,role,password_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (user_id, inv["org_id"], inv["email"], item.name.strip()[:80], inv["role"], hash_password(item.password), ts, ts))
        con.execute("UPDATE invitations SET accepted_at=? WHERE id=?", (ts, inv["id"]))
        token, csrf = _create_session(con, user_id, request)
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        org = con.execute("SELECT * FROM orgs WHERE id=?", (inv["org_id"],)).fetchone()
    _set_cookies(response, token, csrf, max_age=int(float(os.getenv("CFA_SESSION_DAYS", "14")) * 86400))
    _audit_in_org(inv["org_id"], "org.invitation_accepted", inv["email"], {"org_id": inv["org_id"], "role": inv["role"]})
    return {"user": _public_user(row), "org": {"id": org["id"], "name": org["name"], "slug": org["slug"], "plan": org["plan"]},
            "token": token, "csrf": csrf}


@router.patch("/api/org/members/{user_id}")
def set_role(user_id: str, item: RoleIn, request: Request) -> dict[str, Any]:
    p = need(request, "admin")
    if not p.get("org_id"):
        raise HTTPException(400, "no organisation in this session")
    if item.role not in ROLES:
        raise HTTPException(422, "unknown role")
    if item.role == "super_admin" and p["role"] != "super_admin":
        raise HTTPException(403, "only a super admin can create super admins")
    if rank(item.role) >= rank(p["role"]) and p["role"] != "super_admin":
        raise HTTPException(403, "you cannot grant a role at or above your own")
    with db() as con:
        target = con.execute("SELECT * FROM users WHERE id=? AND org_id=?", (user_id, p["org_id"])).fetchone()
        if not target:
            raise HTTPException(404, "member not found")
        if target["role"] == "owner" and p["role"] not in ("owner", "super_admin"):
            raise HTTPException(403, "only the owner can change the owner")
        con.execute("UPDATE users SET role=?, updated_at=? WHERE id=?", (item.role, _now(), user_id))
        con.execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (user_id,))  # role change invalidates sessions
    _audit("org.role_changed", p["name"], {"user_id": user_id, "from": target["role"], "to": item.role})
    return {"ok": True, "user_id": user_id, "role": item.role}


@router.delete("/api/org/members/{user_id}")
def remove_member(user_id: str, request: Request) -> dict[str, bool]:
    p = need(request, "admin")
    if not p.get("org_id"):
        raise HTTPException(400, "no organisation in this session")
    with db() as con:
        target = con.execute("SELECT * FROM users WHERE id=? AND org_id=?", (user_id, p["org_id"])).fetchone()
        if not target:
            raise HTTPException(404, "member not found")
        if target["id"] == p.get("user_id"):
            raise HTTPException(422, "you cannot remove yourself")
        if target["role"] == "owner":
            raise HTTPException(403, "the owner cannot be removed")
        con.execute("UPDATE users SET status='removed', updated_at=? WHERE id=?", (_now(), user_id))
        con.execute("UPDATE sessions SET revoked=1 WHERE user_id=?", (user_id,))
    _audit("org.member_removed", p["name"], {"user_id": user_id})
    return {"ok": True}


def install(app) -> None:
    app.include_router(router)
