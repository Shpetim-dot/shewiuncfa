"""Brain search: SQLite FTS5 keyword ranking (BM25) plus optional semantic ranking from embeddings, fused into one hybrid score.

Permissions are applied in the SQL query, before ranking: an agent only ever sees notes in its own spaces, and only verified notes unless asked otherwise.
Semantic search is a feature flag (CFA_EMBEDDING_MODEL). Without it the API says "keyword" and does not pretend otherwise.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from app import cfa_core as pf

router = APIRouter()


def fts_query(q: str) -> str:
    toks = re.findall(r"[\wäöüß]{2,}", q.lower())[:12]
    return " OR ".join(f'"{t}"*' for t in toks)


def has_fts(con) -> bool:
    return os.getenv("CFA_DISABLE_FTS") != "1" and bool(con.execute("SELECT 1 FROM sqlite_master WHERE name='notes_fts'").fetchone())


def _scan_rows(con, query: str, spaces, k: int, statuses) -> list[Any]:
    """Fallback without FTS5: same filters, simple term scoring in Python (title counts triple). Fine for a pilot-sized Brain."""
    toks = re.findall(r"[\wäöüß]{2,}", query.lower())[:12]
    sp, st = ",".join("?" * len(spaces)), ",".join("?" * len(statuses))
    scored = []
    for r in con.execute(f"SELECT * FROM notes WHERE status IN ({st}) AND space IN ({sp})", (*statuses, *spaces)):
        title, body = (r["title"] or "").lower(), (r["body"] or "").lower()
        score = sum(3 * title.count(t) + body.count(t) for t in toks)
        fl = json.loads(r["flags"] or "[]")
        if score and not ("instruction_like" in fl and "acknowledged" not in fl):
            scored.append({**dict(r), "score": -float(score)})
    return sorted(scored, key=lambda d: d["score"])[:k]


def search_rows(con, query: str, spaces: tuple[str, ...] | list[str], k: int = 6, statuses: tuple[str, ...] = ("verified",)) -> list[Any]:
    fq = fts_query(query)
    if not fq or not spaces:
        return []
    if not has_fts(con):
        return _scan_rows(con, query, spaces, k, statuses)
    sp, st = ",".join("?" * len(spaces)), ",".join("?" * len(statuses))
    try:
        rows = con.execute(f"""SELECT n.*, bm25(notes_fts, 3.0, 1.0) AS score FROM notes_fts JOIN notes n ON n.rowid=notes_fts.rowid
                               WHERE notes_fts MATCH ? AND n.status IN ({st}) AND n.space IN ({sp}) ORDER BY score LIMIT ?""", (fq, *statuses, *spaces, k * 3)).fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        fl = json.loads(r["flags"] or "[]")
        if "instruction_like" in fl and "acknowledged" not in fl:  # possible prompt injection stays out until a human has reviewed it
            continue
        out.append(r)
    return out[:k]


def fuse(keyword: dict[str, float], semantic: dict[str, float], alpha: float = 0.5) -> list[tuple[str, float]]:
    """keyword: higher is better (negated BM25). semantic: cosine similarity. Both are min-max scaled to 0..1, then mixed."""
    def scale(d: dict[str, float]) -> dict[str, float]:
        if not d:
            return {}
        lo, hi = min(d.values()), max(d.values())
        return {k: (1.0 if hi == lo else (v - lo) / (hi - lo)) for k, v in d.items()}
    kw, sm = scale(keyword), scale({k: max(v, 0.0) for k, v in semantic.items()})
    ids = set(kw) | set(sm)
    return sorted(((i, alpha * kw.get(i, 0.0) + (1 - alpha) * sm.get(i, 0.0)) for i in ids), key=lambda x: -x[1])


def cosine(a: list[float], b: list[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


# ---------- embeddings (optional) ----------
def embedding_model() -> str | None:
    return os.getenv("CFA_EMBEDDING_MODEL") or None


async def embed(texts: list[str], model: str) -> list[list[float]]:
    from app import gateway
    prov, base, key, name = pf.resolve_model(model)
    if not key:
        raise HTTPException(503, f"no API key is configured for the '{prov}' provider")
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(transport=pf.LLM_TRANSPORT, timeout=45) as c:
            r = await c.post(f"{base}/embeddings", json={"model": name, "input": texts}, headers={"Authorization": f"Bearer {key}"})
            r.raise_for_status()
            data = r.json()
        vecs = [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
    except (httpx.HTTPError, KeyError, ValueError):
        gateway.record_usage(kind="embedding", bot_id=None, provider=prov, model=name, requested=model, fallback=False, tokens_in=None, tokens_out=None,
                             latency_ms=round((time.monotonic() - t0) * 1000), status="error", error="embedding request failed")
        raise HTTPException(502, "Embedding request failed")
    gateway.record_usage(kind="embedding", bot_id=None, provider=prov, model=name, requested=model, fallback=False, tokens_in=(data.get("usage") or {}).get("prompt_tokens"),
                         tokens_out=0, latency_ms=round((time.monotonic() - t0) * 1000), status="ok")
    return vecs


@router.post("/api/brain/reindex")
async def reindex(request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    model = embedding_model()
    if not model:
        return {"semantic": "off", "indexed": 0, "note": "Keyword index is always current. Set CFA_EMBEDDING_MODEL to enable semantic search."}
    with pf.db() as con:
        notes = con.execute("SELECT id,title,body FROM notes WHERE status IN ('verified','draft')").fetchall()
        have = {r["note_id"]: (r["text_hash"], r["model"]) for r in con.execute("SELECT note_id,text_hash,model FROM note_embeddings")}
    todo = [(n["id"], hashlib.sha256((n["title"] + n["body"]).encode()).hexdigest(), (n["title"] + "\n" + n["body"])[:2000]) for n in notes]
    todo = [t for t in todo if have.get(t[0]) != (t[1], model)]
    done = 0
    for i in range(0, len(todo), 32):
        chunk = todo[i:i + 32]
        vecs = await embed([t[2] for t in chunk], model)
        with pf.db() as con:
            con.executemany("INSERT OR REPLACE INTO note_embeddings VALUES (?,?,?,?)", [(t[0], model, t[1], json.dumps(v)) for t, v in zip(chunk, vecs)])
        done += len(chunk)
    pf._m().append_audit("brain.reindexed", p["name"], {"indexed": done, "model": model})
    return {"semantic": "on", "model": model, "indexed": done, "unchanged": len(notes) - done}


@router.get("/api/brain/search")
async def brain_search(request: Request, q: str, agent: str = "", k: int = 6, include_unverified: bool = False) -> dict[str, Any]:
    p = pf._principal(request)
    k = max(1, min(k, 20))
    statuses = ("verified", "draft") if include_unverified else ("verified",)
    with pf.db() as con:
        if agent:
            row = con.execute("SELECT * FROM bots WHERE id=?", (agent,)).fetchone()
            if not row:
                raise HTTPException(404, "agent not found")
            bot = pf._bot(row)
            if not pf.can(bot, "memory.read"):
                raise HTTPException(403, "agent lacks memory.read or is suspended")
            spaces = tuple(bot["spaces"])
        elif p["role"] == "admin":
            spaces = tuple(r[0] for r in con.execute("SELECT DISTINCT space FROM notes"))
        else:
            spaces = tuple(r[0] for r in con.execute("SELECT DISTINCT space FROM notes") if not str(r[0]).startswith("agent:"))
        kw_rows = search_rows(con, q, spaces, k * 3, statuses)
        keyword = {r["id"]: -r["score"] for r in kw_rows}
        notes = {r["id"]: r for r in kw_rows}
        semantic: dict[str, float] = {}
        mode = "keyword"
        model = embedding_model()
        vecs = {}
        if model and spaces:
            sp = ",".join("?" * len(spaces))
            vecs = {r["id"]: (json.loads(r["vec"]), r) for r in con.execute(
                f"SELECT n.*, e.vec FROM note_embeddings e JOIN notes n ON n.id=e.note_id WHERE e.model=? AND n.space IN ({sp}) AND n.status IN ({','.join('?' * len(statuses))})",
                (model, *spaces, *statuses))}
    if model and vecs:
        try:
            qv = (await embed([q], model))[0]
            for nid, (v, r) in vecs.items():
                fl = json.loads(r["flags"] or "[]")
                if "instruction_like" in fl and "acknowledged" not in fl:
                    continue
                semantic[nid] = cosine(qv, v)
                notes.setdefault(nid, r)
            mode = "hybrid"
        except HTTPException:
            mode = "keyword"  # the embedding provider failed; say so instead of pretending
    ranked = fuse(keyword, semantic)[:k]
    if agent:
        with pf.db() as con:
            for nid, _ in ranked:
                pf.log_brain(con, "read", nid, agent)
    return {"mode": mode, "semantic_configured": bool(model), "query": q, "results": [
        {"id": i, "title": notes[i]["title"], "status": notes[i]["status"], "space": notes[i]["space"], "score": round(s, 4), "snippet": notes[i]["body"][:240],
         "source": notes[i]["source"], "owner": notes[i]["owner"], "verified": notes[i]["status"] == "verified"} for i, s in ranked]}
