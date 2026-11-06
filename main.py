from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sqlite3
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent
if __package__ in (None, "") and importlib.util.find_spec("app") is None:
    # Flat deployment (all .py files next to each other, no "app" folder, e.g. a repo root that holds these files directly):
    # expose this folder as the package "app" so every `from app import ...` keeps working, and make "app.main" this very module.
    _pkg = types.ModuleType("app")
    _pkg.__path__ = [str(HERE)]
    sys.modules["app"] = _pkg
    sys.modules["app.main"] = sys.modules[__name__]

from app.agent_launch import router as agent_launch_router
from app import cfa_core as cfa_platform

load_dotenv()
# Vercel bundles files attached to the Python function. Keep the UI inside the
# app package (app/static) so it is included with app.main; use root static
# as a fallback for local layouts.
ROOT = HERE.parent
STATIC = HERE / "static" if (HERE / "static").is_dir() else ROOT / "static"
# Vercel's deployment bundle is read-only. Use /tmp there even if VERCEL
# is not populated in the function runtime or CFA_DATABASE_PATH points into the bundle.
IS_VERCEL = bool(
    os.getenv("VERCEL")
    or os.getenv("VERCEL_ENV")
    or os.getenv("VERCEL_URL")
    or str(ROOT).startswith("/var/task")
)
configured_db_path = os.getenv("CFA_DATABASE_PATH")
if IS_VERCEL:
    DB_PATH = Path("/tmp/cfa.db")
else:
    DB_PATH = Path(configured_db_path or "./data/cfa.db")
if not DB_PATH.is_absolute():
    DB_PATH = ROOT / DB_PATH
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Shewiun CFA", version="0.2.0", description="Control & Focus Architecture")
if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
app.include_router(agent_launch_router)
cfa_platform.install(app)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    # A short lock wait prevents transient concurrent writes from failing immediately.
    # Foreign-key enforcement is connection-local in SQLite, so enable it consistently.
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 15000")
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")  # readers do not block the writer; needed for consistent online backups
    db.execute("PRAGMA synchronous = NORMAL")
    return db


def init_db() -> None:
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'Active', created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS brain (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, content TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'Fact', source TEXT NOT NULL DEFAULT 'User input',
          confidence INTEGER NOT NULL DEFAULT 80, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS council (
          id TEXT PRIMARY KEY, topic TEXT NOT NULL, result TEXT NOT NULL,
          transcript TEXT NOT NULL, mode TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS activity (
          id TEXT PRIMARY KEY, action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL, event_type TEXT NOT NULL,
          actor TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS approval_requests (
          id TEXT PRIMARY KEY, action_type TEXT NOT NULL, description TEXT NOT NULL, requested_by TEXT NOT NULL,
          risk_level TEXT NOT NULL, status TEXT NOT NULL, decision_by TEXT, decision_note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL, decided_at TEXT
        );
        CREATE TABLE IF NOT EXISTS runtime_runs (
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, input_json TEXT NOT NULL,
          state_json TEXT NOT NULL, result_json TEXT, error TEXT, attempt INTEGER NOT NULL DEFAULT 0,
          max_attempts INTEGER NOT NULL DEFAULT 3, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          started_at TEXT, finished_at TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_runtime_runs_status_created ON runtime_runs(status, created_at);
        CREATE TABLE IF NOT EXISTS runtime_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(run_id) REFERENCES runtime_runs(id)
        );
        """)
        if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
            db.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)", (
                "proj-cfa", "Shewiun CFA MVP", "Build the control center for collaborative AI agents.", "Active", now()
            ))
        if db.execute("SELECT COUNT(*) FROM brain").fetchone()[0] == 0:
            samples = [
                ("CFA principle", "CFA coordinates external models and agents; it is not itself a new foundation model.", "Rule", "Product brief", 95),
                ("Shared knowledge", "Knowledge entries should keep their source and confidence visible.", "Decision", "Product brief", 90),
                ("Human oversight", "High-impact actions should require explicit human approval.", "Rule", "Security baseline", 95),
            ]
            for title, content, kind, source, confidence in samples:
                db.execute("INSERT INTO brain VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (str(uuid4()), title, content, kind, source, confidence, now()))
        if db.execute("SELECT COUNT(*) FROM activity").fetchone()[0] == 0:
            db.execute("INSERT INTO activity VALUES (?, ?, ?, ?)",
                       (str(uuid4()), "Workspace initialized", "CFA local workspace is ready.", now()))


_runtime_worker_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup() -> None:
    global _runtime_worker_task
    init_db()
    # Single-process SQLite MVP: recover interrupted runs after restart.
    with connect() as db:
        db.execute("UPDATE runtime_runs SET status='queued', updated_at=?, error=NULL WHERE status='running'", (now(),))
    _runtime_worker_task = asyncio.create_task(runtime_worker())


@app.on_event("shutdown")
async def shutdown() -> None:
    global _runtime_worker_task
    if _runtime_worker_task:
        _runtime_worker_task.cancel()
        try:
            await _runtime_worker_task
        except asyncio.CancelledError:
            pass
        _runtime_worker_task = None


def append_audit(event_type: str, actor: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a hash-linked audit event. This detects edits to the chain; it is not a signed external ledger."""
    created_at = now()
    event_id = str(uuid4())
    canonical_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    with connect() as db:
        row = db.execute("SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        previous_hash = row["event_hash"] if row else "GENESIS"
        material = json.dumps({
            "id": event_id, "event_type": event_type, "actor": actor, "payload": json.loads(canonical_payload),
            "previous_hash": previous_hash, "created_at": created_at
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        import hashlib
        event_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        db.execute(
            "INSERT INTO audit_events (id,event_type,actor,payload,previous_hash,event_hash,created_at) VALUES (?,?,?,?,?,?,?)",
            (event_id, event_type, actor, canonical_payload, previous_hash, event_hash, created_at)
        )
    return {"id": event_id, "event_type": event_type, "actor": actor, "payload": payload,
            "previous_hash": previous_hash, "event_hash": event_hash, "created_at": created_at}


def log(action: str, detail: str) -> None:
    with connect() as db:
        db.execute("INSERT INTO activity VALUES (?, ?, ?, ?)", (str(uuid4()), action, detail, now()))
    append_audit("workspace.activity", "system", {"action": action, "detail": detail})


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class BrainIn(BaseModel):
    title: str = Field(min_length=1, max_length=140)
    content: str = Field(min_length=1, max_length=5000)
    kind: str = Field(default="Fact", max_length=40)
    source: str = Field(default="User input", max_length=200)
    confidence: int = Field(default=80, ge=0, le=100)


class CouncilIn(BaseModel):
    topic: str = Field(min_length=3, max_length=4000)
    roles: list[str] = Field(default_factory=lambda: ["Strategist", "Skeptic", "Builder"])
    rounds: int = Field(default=1, ge=1, le=2)


@app.get("/")
def home() -> HTMLResponse:
    if not (STATIC / "index.html").is_file():  # say what is wrong instead of failing with a bare 500
        return HTMLResponse("<h1>Shewiun CFA</h1><p>The API is running, but the <code>static</code> folder was not deployed. Upload the whole project folder (app, static, requirements.txt).</p>", status_code=503)
    # The version in the asset URLs makes browsers fetch the new files after every release.
    return HTMLResponse((STATIC / "index.html").read_text(encoding="utf-8").replace("__V__", cfa_platform.VERSION))


@app.get("/welcome")
def welcome() -> FileResponse:
    return FileResponse(STATIC / "welcome.html")


@app.get("/trust")
def trust() -> FileResponse:
    return FileResponse(STATIC / "trust.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": "Shewiun CFA",
        "version": "0.2.0",
        "model_configured": cfa_platform.live(),
        "auth": "enabled" if cfa_platform.auth_enabled() else "disabled",
        "warnings": cfa_platform.warnings(),
        "version": cfa_platform.VERSION,
        "billing": os.getenv("CFA_BILLING") == "on",
        "logo_cdn": os.getenv("CFA_LOGO_CDN", "https://cdn.simpleicons.org"),
        "build": (os.getenv("VERCEL_GIT_COMMIT_SHA") or os.getenv("CFA_BUILD") or "")[:7],
        "search_configured": bool(os.getenv("CFA_SEARCH_API_KEY")),
        "secret_key_configured": bool(os.getenv("CFA_SECRET_KEY")),
        "storage": "ephemeral_sqlite" if IS_VERCEL else "sqlite",
        "storage_warning": (
            "Vercel /tmp storage is ephemeral; data may be lost between instances or deployments."
            if IS_VERCEL else None
        ),
    }


@app.get("/api/projects")
def list_projects() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created_at DESC")]


@app.post("/api/projects")
def create_project(item: ProjectIn) -> dict[str, Any]:
    record = {"id": str(uuid4()), "name": item.name.strip(), "description": item.description.strip(),
              "status": "Active", "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO projects VALUES (:id, :name, :description, :status, :created_at)", record)
    log("Project created", record["name"])
    return record


@app.get("/api/brain")
def list_brain() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM brain ORDER BY created_at DESC")]


@app.post("/api/brain")
def create_brain(item: BrainIn) -> dict[str, Any]:
    record = {"id": str(uuid4()), **item.model_dump(), "title": item.title.strip(),
              "content": item.content.strip(), "source": item.source.strip(), "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO brain VALUES (:id, :title, :content, :kind, :source, :confidence, :created_at)", record)
    log("Brain entry added", record["title"])
    return record


AGENTS = [
    {"id": "strategist", "name": "Strategist", "role": "Direction & priorities", "provider": "CFA demo", "status": "Ready", "color": "violet"},
    {"id": "skeptic", "name": "Skeptic", "role": "Risks & counterarguments", "provider": "CFA demo", "status": "Ready", "color": "amber"},
    {"id": "builder", "name": "Builder", "role": "Implementation & next steps", "provider": "CFA demo", "status": "Ready", "color": "mint"},
    {"id": "synthesizer", "name": "Synthesizer", "role": "Decision & summary", "provider": "CFA demo", "status": "Ready", "color": "blue"},
]


@app.get("/api/agents")
def list_agents() -> list[dict[str, str]]:
    live = bool(os.getenv("CFA_MODEL_API_KEY"))
    return [{**a, "provider": os.getenv("CFA_MODEL_NAME", "Configured model") if live else "Local demo",
             "status": "Connected" if live else "Demo mode"} for a in AGENTS]


async def model_reply(role: str, topic: str, context: str) -> str | None:
    key = os.getenv("CFA_MODEL_API_KEY")
    if not key:
        return None
    base = os.getenv("CFA_MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("CFA_MODEL_NAME", "gpt-4o-mini")
    system = {
        "Strategist": "You are the Strategist in a multi-agent product council. Identify the opportunity, desired outcome, and priorities. Be concise.",
        "Skeptic": "You are the Skeptic in a multi-agent product council. Challenge assumptions, identify risks, and suggest mitigations. Be constructive.",
        "Builder": "You are the Builder in a multi-agent product council. Turn the discussion into practical steps, dependencies, and an MVP scope.",
        "Synthesizer": "You are the Council Synthesizer. Resolve disagreement, state the strongest shared conclusion, open questions, and next actions."
    }.get(role, f"You are the {role} in a product council. Be concise and specific.")
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "system", "content": system},
                  {"role": "user", "content": f"Topic: {topic}\n\nContext from previous speakers:\n{context or '(first speaker)'}"}],
                  "temperature": 0.5})
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


def demo_reply(role: str, topic: str, context: str) -> str:
    snippets = {
        "Strategist": f"Frame “{topic}” around one measurable outcome. Start with the smallest workflow that demonstrates user value, then expand only after validating adoption.",
        "Skeptic": "Main risks: unclear success criteria, hidden integration costs, and too much automation before trust is earned. Define a baseline, show sources, and keep consequential actions behind human approval.",
        "Builder": "Proposed sequence: (1) define the target user and acceptance criteria, (2) build one end-to-end path, (3) record decisions and evidence, (4) test with real tasks, (5) prioritize from observed friction.",
        "Synthesizer": "Recommendation: run a narrow, measurable pilot. Align on the success metric, document assumptions in CFA Brain, assign one owner per action, and review evidence before increasing scope."
    }
    return snippets.get(role, f"Assess “{topic}” from the perspective of {role}. State the key recommendation, assumptions, and next action.")


@app.post("/api/council")
async def start_council(item: CouncilIn) -> dict[str, Any]:
    roles = [r for r in item.roles if r in {"Strategist", "Skeptic", "Builder"}]
    if not roles:
        roles = ["Strategist", "Skeptic", "Builder"]
    if "Synthesizer" not in roles:
        roles.append("Synthesizer")
    transcript: list[dict[str, str]] = []
    context = ""
    live = bool(os.getenv("CFA_MODEL_API_KEY"))
    try:
        for _ in range(item.rounds):
            for role in roles:
                reply = await model_reply(role, item.topic, context) if live else None
                if reply is None:
                    reply = demo_reply(role, item.topic, context)
                transcript.append({"role": role, "content": reply})
                context += f"\n{role}: {reply}"
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Configured model request failed: {exc}") from exc
    result = next((m["content"] for m in reversed(transcript) if m["role"] == "Synthesizer"), transcript[-1]["content"])
    record = {"id": str(uuid4()), "topic": item.topic, "result": result,
              "transcript": json.dumps(transcript, ensure_ascii=False), "mode": "live" if live else "demo",
              "created_at": now()}
    with connect() as db:
        db.execute("INSERT INTO council VALUES (:id, :topic, :result, :transcript, :mode, :created_at)", record)
    log("Council completed", item.topic[:180])
    return {**record, "transcript": transcript}


@app.get("/api/council")
def list_councils() -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute("SELECT * FROM council ORDER BY created_at DESC LIMIT 10").fetchall()
    return [{**dict(r), "transcript": json.loads(r["transcript"])} for r in rows]


@app.get("/api/activity")
def list_activity() -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM activity ORDER BY created_at DESC LIMIT 20")]


# --- CFA Security: policy decisions, human approvals and verifiable audit chain ---

RISK_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}
POLICY_DEFAULTS = {
    "project.create": "allow",
    "brain.write": "allow",
    "council.run": "allow",
    "external.write": "approval_required",
    "external.delete": "approval_required",
    "secrets.read": "deny",
    "shell.execute": "deny",
}


class ApprovalIn(BaseModel):
    action_type: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=3, max_length=2000)
    requested_by: str = Field(default="workspace-owner", min_length=1, max_length=100)
    risk_level: str = Field(default="high")


class ApprovalDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    decided_by: str = Field(min_length=1, max_length=100)
    note: str = Field(default="", max_length=1000)


def verify_audit_chain() -> dict[str, Any]:
    import hashlib
    expected_previous = "GENESIS"
    checked = 0
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_events ORDER BY seq ASC").fetchall()
    for row in rows:
        payload = json.loads(row["payload"])
        material = json.dumps({
            "id": row["id"], "event_type": row["event_type"], "actor": row["actor"], "payload": payload,
            "previous_hash": row["previous_hash"], "created_at": row["created_at"]
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        calculated = hashlib.sha256(material.encode("utf-8")).hexdigest()
        if row["previous_hash"] != expected_previous or row["event_hash"] != calculated:
            return {"valid": False, "checked": checked, "failed_event_id": row["id"]}
        expected_previous = row["event_hash"]
        checked += 1
    return {"valid": True, "checked": checked, "head": expected_previous}


@app.get("/api/security/policies")
def security_policies() -> dict[str, Any]:
    return {
        "default_effect": "deny for unknown action types",
        "policies": [{"action_type": k, "decision": v} for k, v in POLICY_DEFAULTS.items()],
        "note": "Policy reference layer for the MVP; no external tools are executed."
    }


@app.get("/api/security/audit")
def security_audit(limit: int = 50) -> dict[str, Any]:
    limit = max(1, min(limit, 200))
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
    return {"integrity": verify_audit_chain(), "events": [
        {**dict(r), "payload": json.loads(r["payload"])} for r in rows
    ]}


@app.post("/api/security/approvals")
def request_approval(item: ApprovalIn) -> dict[str, Any]:
    risk = item.risk_level.lower()
    if risk not in RISK_LEVELS:
        raise HTTPException(status_code=422, detail="risk_level must be low, medium, high, or critical")
    policy = POLICY_DEFAULTS.get(item.action_type, "deny")
    if policy == "deny":
        status = "rejected"
    elif policy == "approval_required" or RISK_LEVELS[risk] >= 3:
        status = "pending"
    else:
        status = "approved"
    record = {
        "id": str(uuid4()), "action_type": item.action_type, "description": item.description.strip(),
        "requested_by": item.requested_by, "risk_level": risk, "status": status,
        "decision_by": "policy-engine" if status != "pending" else None,
        "decision_note": "Policy decision: " + policy, "created_at": now(),
        "decided_at": now() if status != "pending" else None
    }
    with connect() as db:
        db.execute(
            "INSERT INTO approval_requests (id,action_type,description,requested_by,risk_level,status,decision_by,decision_note,created_at,decided_at) VALUES (:id,:action_type,:description,:requested_by,:risk_level,:status,:decision_by,:decision_note,:created_at,:decided_at)",
            record
        )
    append_audit("approval.requested", item.requested_by, {
        "approval_id": record["id"], "action_type": item.action_type, "risk_level": risk, "status": status
    })
    log("Approval " + status, item.action_type + ": " + item.description[:150])
    return record


@app.get("/api/security/approvals")
def list_approvals(status: str | None = None) -> list[dict[str, Any]]:
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM approval_requests WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = db.execute("SELECT * FROM approval_requests ORDER BY created_at DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


@app.post("/api/security/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, item: ApprovalDecisionIn, request: Request) -> dict[str, Any]:
    # The decider is the authenticated admin, never a name taken from the request body.
    item.decided_by = cfa_platform.need_admin(request)["name"]
    with connect() as db:
        row = db.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Approval request not found")
        if row["status"] != "pending":
            raise HTTPException(status_code=409, detail="Approval request has already been decided")
        decided_at = now()
        db.execute(
            "UPDATE approval_requests SET status=?, decision_by=?, decision_note=?, decided_at=? WHERE id=? AND status='pending'",
            (item.decision, item.decided_by, item.note, decided_at, approval_id)
        )
        record = dict(db.execute("SELECT * FROM approval_requests WHERE id=?", (approval_id,)).fetchone())
    append_audit("approval." + item.decision, item.decided_by, {
        "approval_id": approval_id, "action_type": record["action_type"], "note": item.note
    })
    log("Approval " + item.decision, record["action_type"] + " decided by " + item.decided_by)
    return record


@app.get("/api/security/audit/verify")
def audit_verify() -> dict[str, Any]:
    return verify_audit_chain()

# --- CFA Agent Runtime: durable queue, per-speaker checkpoints, bounded retries ---

RUNTIME_ROLES = ("Strategist", "Skeptic", "Builder", "Synthesizer")
_RUNTIME_POLL_SECONDS = 0.75

def _runtime_event(run_id: str, event_type: str, payload: dict[str, Any]) -> None:
    with connect() as db:
        db.execute("INSERT INTO runtime_events (run_id,event_type,payload_json,created_at) VALUES (?,?,?,?)",
                   (run_id, event_type, json.dumps(payload, ensure_ascii=False), now()))

def _runtime_run(row: sqlite3.Row, include_state: bool = True) -> dict[str, Any]:
    item = dict(row)
    item["input"] = json.loads(item.pop("input_json"))
    state = json.loads(item.pop("state_json"))
    if include_state:
        item["state"] = state
    result_json = item.pop("result_json")
    item["result"] = json.loads(result_json) if result_json else None
    item["cancel_requested"] = bool(item["cancel_requested"])
    return item

async def _execute_runtime_run(run_id: str) -> None:
    with connect() as db:
        row = db.execute("SELECT * FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
    if not row or row["status"] != "running":
        return
    item = _runtime_run(row)
    request, state = item["input"], item["state"]
    roles, transcript = state["roles"], state["transcript"]
    live = bool(os.getenv("CFA_MODEL_API_KEY"))
    try:
        while state["next_index"] < len(roles):
            with connect() as db:
                current = db.execute("SELECT status,cancel_requested FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
            if not current or current["cancel_requested"] or current["status"] == "cancelled":
                with connect() as db:
                    db.execute("UPDATE runtime_runs SET status='cancelled',updated_at=?,finished_at=? WHERE id=?", (now(), now(), run_id))
                _runtime_event(run_id, "run.cancelled", {"completed_steps": len(transcript)})
                return
            role = roles[state["next_index"]]
            context = "\n".join(f"{m['role']}: {m['content']}" for m in transcript)
            reply = await model_reply(role, request["topic"], context) if live else None
            if reply is None:
                reply = demo_reply(role, request["topic"], context)
            transcript.append({"role": role, "content": reply, "step": state["next_index"]})
            state["next_index"] += 1
            state["transcript"] = transcript
            # Persist after every completed speaker; restart resumes from next_index.
            with connect() as db:
                db.execute("UPDATE runtime_runs SET state_json=?,updated_at=? WHERE id=? AND status='running'",
                           (json.dumps(state, ensure_ascii=False), now(), run_id))
            _runtime_event(run_id, "step.completed", {"index": state["next_index"] - 1, "role": role})
        result = next((m["content"] for m in reversed(transcript) if m["role"] == "Synthesizer"),
                      transcript[-1]["content"] if transcript else "")
        result_record = {"topic": request["topic"], "result": result, "transcript": transcript,
                         "mode": "live" if live else "demo"}
        with connect() as db:
            db.execute("UPDATE runtime_runs SET status='completed',result_json=?,updated_at=?,finished_at=?,error=NULL WHERE id=? AND status='running'",
                       (json.dumps(result_record, ensure_ascii=False), now(), now(), run_id))
            db.execute("INSERT INTO council VALUES (?, ?, ?, ?, ?, ?)",
                       (run_id, request["topic"], result, json.dumps(transcript, ensure_ascii=False), result_record["mode"], now()))
        _runtime_event(run_id, "run.completed", {"mode": result_record["mode"], "steps": len(transcript)})
        log("Council runtime completed", request["topic"][:180])
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        with connect() as db:
            row = db.execute("SELECT attempt,max_attempts FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
            if row and row["attempt"] < row["max_attempts"]:
                db.execute("UPDATE runtime_runs SET status='queued',error=?,updated_at=? WHERE id=?",
                           (str(exc)[:1000], now(), run_id))
                event_type = "run.retry_scheduled"
            else:
                db.execute("UPDATE runtime_runs SET status='failed',error=?,updated_at=?,finished_at=? WHERE id=?",
                           (str(exc)[:1000], now(), now(), run_id))
                event_type = "run.failed"
        _runtime_event(run_id, event_type, {"error": str(exc)[:500]})
        if event_type == "run.failed":
            log("Council runtime failed", f"{run_id}: {str(exc)[:120]}")

async def runtime_worker() -> None:
    # SQLite runtime intentionally supports one app worker process at a time.
    while True:
        run_id = None
        with connect() as db:
            row = db.execute("SELECT id FROM runtime_runs WHERE status='queued' ORDER BY created_at ASC LIMIT 1").fetchone()
            if row:
                run_id = row["id"]
                changed = db.execute("UPDATE runtime_runs SET status='running',attempt=attempt+1,started_at=COALESCE(started_at,?),updated_at=? WHERE id=? AND status='queued'",
                                     (now(), now(), run_id)).rowcount
                if not changed:
                    run_id = None
        if run_id:
            _runtime_event(run_id, "run.started", {})
            await _execute_runtime_run(run_id)
        else:
            await asyncio.sleep(_RUNTIME_POLL_SECONDS)

class RuntimeCouncilIn(BaseModel):
    topic: str = Field(min_length=3, max_length=4000)
    roles: list[str] = Field(default_factory=lambda: ["Strategist", "Skeptic", "Builder"])
    rounds: int = Field(default=1, ge=1, le=2)
    max_attempts: int = Field(default=3, ge=1, le=5)

@app.post("/api/runtime/runs", status_code=202)
def create_runtime_run(item: RuntimeCouncilIn) -> dict[str, Any]:
    roles = [role for role in item.roles if role in {"Strategist", "Skeptic", "Builder"}]
    if not roles:
        roles = ["Strategist", "Skeptic", "Builder"]
    if "Synthesizer" not in roles:
        roles.append("Synthesizer")
    expanded_roles = roles * item.rounds
    run_id, timestamp = str(uuid4()), now()
    request = {"topic": item.topic.strip(), "roles": roles, "rounds": item.rounds}
    state = {"roles": expanded_roles, "next_index": 0, "transcript": []}
    with connect() as db:
        db.execute("INSERT INTO runtime_runs (id,kind,status,input_json,state_json,attempt,max_attempts,created_at,updated_at) VALUES (?,?,?,?,?,0,?,?,?)",
                   (run_id, "council", "queued", json.dumps(request, ensure_ascii=False), json.dumps(state, ensure_ascii=False), item.max_attempts, timestamp, timestamp))
    _runtime_event(run_id, "run.queued", {"kind": "council", "steps": len(expanded_roles)})
    append_audit("runtime.run.queued", "workspace-owner", {"run_id": run_id, "kind": "council"})
    return {"id": run_id, "kind": "council", "status": "queued", "created_at": timestamp, "poll_url": f"/api/runtime/runs/{run_id}"}

@app.get("/api/runtime/runs")
def list_runtime_runs(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 200))
    with connect() as db:
        if status:
            rows = db.execute("SELECT * FROM runtime_runs WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit)).fetchall()
        else:
            rows = db.execute("SELECT * FROM runtime_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_runtime_run(row) for row in rows]

@app.get("/api/runtime/runs/{run_id}")
def get_runtime_run(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runtime run not found")
        events = db.execute("SELECT event_type,payload_json,created_at FROM runtime_events WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
    result = _runtime_run(row)
    result["events"] = [{**dict(e), "payload": json.loads(e["payload_json"])} for e in events]
    return result

@app.post("/api/runtime/runs/{run_id}/retry", status_code=202)
def retry_runtime_run(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runtime run not found")
        if row["status"] not in {"failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Only failed or cancelled runs can be retried")
        state = json.loads(row["state_json"])
        db.execute("UPDATE runtime_runs SET status='queued',error=NULL,finished_at=NULL,cancel_requested=0,updated_at=? WHERE id=?", (now(), run_id))
    _runtime_event(run_id, "run.requeued", {"resume_from_step": state["next_index"]})
    return {"id": run_id, "status": "queued", "resume_from_step": state["next_index"]}

@app.post("/api/runtime/runs/{run_id}/cancel")
def cancel_runtime_run(run_id: str) -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT status FROM runtime_runs WHERE id=?", (run_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Runtime run not found")
        if row["status"] in {"completed", "failed", "cancelled"}:
            raise HTTPException(status_code=409, detail="Run is already terminal")
        db.execute("UPDATE runtime_runs SET cancel_requested=1,updated_at=? WHERE id=?", (now(), run_id))
    _runtime_event(run_id, "run.cancel_requested", {})
    return {"id": run_id, "status": "cancellation_requested"}
