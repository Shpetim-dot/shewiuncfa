"""Model providers: a default OpenAI-compatible endpoint plus Hugging Face Inference Providers (free tier with monthly credits)."""
from __future__ import annotations

import os
import re
import time
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import cfa_core as pf

router = APIRouter()
SUGGESTED = [
    {"id": "hf:MiniMaxAI/MiniMax-M2", "name": "MiniMax-M2", "note": "Open-weight agentic model; third-party guides show it on the Hugging Face router"},
    {"id": "hf:openai/gpt-oss-120b", "name": "gpt-oss-120b", "note": "Open-weight reasoning model on the router"},
    {"id": "hf:Qwen/Qwen3-8B", "name": "Qwen3 8B", "note": "Small and fast, good for the free tier"},
    {"id": "hf:deepseek-ai/DeepSeek-V3.2", "name": "DeepSeek V3.2", "note": "Large general model"},
    {"id": "hf:moonshotai/Kimi-K2-Instruct-0905", "name": "Kimi K2", "note": "Used in Hugging Face's own getting-started guide"},
]
MODEL_ID = re.compile(r"^((hf|openai):)?[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,118}$")


@router.get("/api/models")
def models(request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    default_key = bool(os.getenv("CFA_MODEL_API_KEY"))
    return {"providers": [
        {"id": "default", "name": "OpenAI-compatible endpoint", "configured": default_key, "host": urlparse(os.getenv("CFA_MODEL_BASE_URL", "https://api.openai.com/v1")).netloc, "model": os.getenv("CFA_MODEL_NAME", "gpt-4o-mini"), "env": "CFA_MODEL_API_KEY, CFA_MODEL_BASE_URL, CFA_MODEL_NAME"},
        {"id": "hf", "name": "Hugging Face Inference Providers", "configured": bool(os.getenv("HF_TOKEN") or os.getenv("CFA_HF_TOKEN")), "host": "router.huggingface.co", "model": "any model id, prefix hf:", "env": "HF_TOKEN"}],
        "suggested": SUGGESTED, "max_tokens": int(os.getenv("CFA_MAX_TOKENS", "700")),
        "free_tier_note": "Hugging Face's free tier gives monthly inference credits with rate limits. Heavier use needs a PRO plan or pay-as-you-go. Check router.huggingface.co/v1/models for what your account can use."}


class TestIn(BaseModel):
    model: str | None = Field(default=None, max_length=120)


@router.post("/api/models/test")
async def test_model(item: TestIn, request: Request) -> dict[str, Any]:
    pf.need_admin(request)
    if item.model and not MODEL_ID.match(item.model):
        raise HTTPException(422, "invalid model id")
    prov, _, key, name = pf.resolve_model(item.model)
    if not key:
        return {"ok": False, "provider": prov, "model": name, "message": f"No API key for the '{prov}' provider. Set {'HF_TOKEN' if prov == 'hf' else 'CFA_MODEL_API_KEY'}."}
    t0 = time.monotonic()
    try:
        text = await pf.llm("Reply with the single word: ok", "ping", item.model, {"kind": "test"})
    except HTTPException as e:
        return {"ok": False, "provider": prov, "model": name, "message": str(e.detail)}
    return {"ok": True, "provider": prov, "model": name, "ms": round((time.monotonic() - t0) * 1000), "reply": text[:80]}


class BotModelIn(BaseModel):
    model: str = Field(default="", max_length=120)


@router.put("/api/bots/{bot_id}/model")
def set_bot_model(bot_id: str, item: BotModelIn, request: Request) -> dict[str, Any]:
    p = pf.need_admin(request)
    if item.model and not MODEL_ID.match(item.model):
        raise HTTPException(422, "model id must look like hf:owner/model or a plain model name")
    with pf.db() as con:
        if not con.execute("SELECT 1 FROM bots WHERE id=?", (bot_id,)).fetchone():
            raise HTTPException(404, "agent not found")
        con.execute("UPDATE bots SET model=? WHERE id=?", (item.model or None, bot_id))
    pf._m().append_audit("agent.model.changed", p["name"], {"agent": bot_id, "model": item.model or "default"})
    return {"id": bot_id, "model": item.model or None, "live": pf.model_live(item.model or None)}
