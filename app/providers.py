"""Model provider adapters.

Three wire formats are supported behind one call:

* `openai`     — any OpenAI-compatible `/chat/completions` endpoint (OpenAI, Mistral, vLLM,
                 LiteLLM, Hugging Face router, self-hosted gateways)
* `anthropic`  — Claude Messages API (`/v1/messages`, `x-api-key`, `anthropic-version`)
* `google`     — Gemini `generateContent` (`/v1beta/models/{model}:generateContent`)

Model ids select the adapter explicitly with a prefix (`anthropic:claude-...`,
`gemini:gemini-2.5-pro`, `openai:gpt-...`) or by name pattern. Everything returns
`(text, usage)` where usage keys are normalised to `tokens_in` / `tokens_out`, so the cost
record in `gateway.record_usage` stays comparable across providers.

Keys come from the environment only:
    CFA_MODEL_API_KEY   default OpenAI-compatible endpoint
    ANTHROPIC_API_KEY   (or CFA_ANTHROPIC_KEY)
    GEMINI_API_KEY      (or CFA_GEMINI_KEY, GOOGLE_API_KEY)
    HF_TOKEN            Hugging Face router
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx

ANTHROPIC_BASE = "https://api.anthropic.com"
GEMINI_BASE = "https://generativelanguage.googleapis.com"
ANTHROPIC_VERSION = "2023-06-01"

# Model-name hints, only used when the id has no explicit prefix.
_ANTHROPIC_HINT = re.compile(r"^(claude|anthropic/)", re.I)
_GEMINI_HINT = re.compile(r"^(gemini|models/gemini|google/)", re.I)


def strip_prefix(model: str) -> tuple[str | None, str]:
    """Split `provider:model` into (provider or None, model)."""
    if ":" in model:
        head, _, rest = model.partition(":")
        if head.lower() in ("anthropic", "claude"):
            return "anthropic", rest
        if head.lower() in ("gemini", "google"):
            return "google", rest
        if head.lower() in ("openai", "hf"):
            return "openai", rest
        return None, model  # a registered provider id: handled by the gateway
    return None, model


def kind_of(model: str) -> str:
    explicit, name = strip_prefix(model)
    if explicit:
        return explicit
    if _ANTHROPIC_HINT.match(name):
        return "anthropic"
    if _GEMINI_HINT.match(name):
        return "google"
    return "openai"


def key_for(kind: str) -> str | None:
    if kind == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("CFA_ANTHROPIC_KEY")
    if kind == "google":
        return os.getenv("GEMINI_API_KEY") or os.getenv("CFA_GEMINI_KEY") or os.getenv("GOOGLE_API_KEY")
    return os.getenv("CFA_MODEL_API_KEY")


def base_for(kind: str, fallback: str) -> str:
    if kind == "anthropic":
        return (os.getenv("CFA_ANTHROPIC_BASE_URL") or ANTHROPIC_BASE).rstrip("/")
    if kind == "google":
        return (os.getenv("CFA_GEMINI_BASE_URL") or GEMINI_BASE).rstrip("/")
    return fallback.rstrip("/")


def configured() -> list[str]:
    return [k for k in ("openai", "anthropic", "google") if key_for(k)] + (
        ["hf"] if (os.getenv("HF_TOKEN") or os.getenv("CFA_HF_TOKEN")) else [])


def _text_of_anthropic(data: dict[str, Any]) -> str:
    parts = [b.get("text", "") for b in (data.get("content") or []) if b.get("type") == "text"]
    return "\n".join(p for p in parts if p).strip()


def _text_of_gemini(data: dict[str, Any]) -> str:
    out = []
    for cand in data.get("candidates") or []:
        for part in ((cand.get("content") or {}).get("parts") or []):
            if part.get("text"):
                out.append(part["text"])
    return "\n".join(out).strip()


async def complete(*, kind: str, base: str, key: str, model: str, system: str, user: str,
                   max_tokens: int, temperature: float, transport: httpx.AsyncBaseTransport | None = None,
                   timeout: float = 45.0) -> tuple[str, dict[str, int | None]]:
    """One request in the provider's native wire format. Raises httpx errors; the caller maps them."""
    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        if kind == "anthropic":
            r = await client.post(f"{base}/v1/messages",
                                  headers={"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION,
                                           "content-type": "application/json"},
                                  json={"model": model, "max_tokens": max_tokens, "temperature": temperature,
                                        "system": system, "messages": [{"role": "user", "content": user}]})
            r.raise_for_status()
            data = r.json()
            u = data.get("usage") or {}
            return _text_of_anthropic(data), {"tokens_in": u.get("input_tokens"), "tokens_out": u.get("output_tokens")}

        if kind == "google":
            r = await client.post(f"{base}/v1beta/models/{model}:generateContent",
                                  headers={"x-goog-api-key": key, "content-type": "application/json"},
                                  json={"system_instruction": {"parts": [{"text": system}]},
                                        "contents": [{"role": "user", "parts": [{"text": user}]}],
                                        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}})
            r.raise_for_status()
            data = r.json()
            u = data.get("usageMetadata") or {}
            return _text_of_gemini(data), {"tokens_in": u.get("promptTokenCount"), "tokens_out": u.get("candidatesTokenCount")}

        # OpenAI-compatible default
        r = await client.post(f"{base}/chat/completions",
                              headers={"Authorization": f"Bearer {key}"},
                              json={"model": model, "temperature": temperature, "max_tokens": max_tokens,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]})
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage") or {}
        return (text or "").strip(), {"tokens_in": u.get("prompt_tokens"), "tokens_out": u.get("completion_tokens")}
