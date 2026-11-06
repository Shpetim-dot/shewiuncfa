"""Provider adapters: native Anthropic and Gemini wire formats behind the gateway."""
import asyncio
import functools
import json

import httpx
import pytest

from app import cfa_core as pf
from app import providers


def run_async(fn):
    """Run an async test without pytest-asyncio (the project has no async plugin)."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))

    return wrapper


def test_model_ids_select_the_adapter():
    assert providers.kind_of("anthropic:claude-opus-4-7") == "anthropic"
    assert providers.kind_of("claude-sonnet-4-5") == "anthropic"
    assert providers.kind_of("gemini:gemini-2.5-pro") == "google"
    assert providers.kind_of("gemini-2.5-flash") == "google"
    assert providers.kind_of("gpt-4o-mini") == "openai"
    assert providers.kind_of("hf:openai/gpt-oss-120b") == "openai"
    assert providers.kind_of("acme:my-model") == "openai"


def test_resolve_model_uses_native_base_and_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gm-test")
    prov, base, key, name = pf.resolve_model("anthropic:claude-opus-4-7")
    assert (prov, key, name) == ("anthropic", "sk-ant-test", "claude-opus-4-7")
    assert base.startswith("https://api.anthropic.com")
    prov, base, key, name = pf.resolve_model("gemini:gemini-2.5-pro")
    assert (prov, key, name) == ("google", "gm-test", "gemini-2.5-pro")
    assert "generativelanguage" in base
    assert pf.live() is True


@run_async
async def test_anthropic_wire_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": " hello "}],
                                         "usage": {"input_tokens": 11, "output_tokens": 7}})

    text, usage = await providers.complete(kind="anthropic", base="https://api.anthropic.com", key="sk-ant",
                                           model="claude-opus-4-7", system="sys", user="hi", max_tokens=100,
                                           temperature=0.2, transport=httpx.MockTransport(handler))
    assert text == "hello"
    assert usage == {"tokens_in": 11, "tokens_out": 7}
    assert seen["url"].endswith("/v1/messages")
    assert seen["headers"]["x-api-key"] == "sk-ant"
    assert seen["headers"]["anthropic-version"]
    assert seen["body"]["system"] == "sys" and seen["body"]["messages"][0]["content"] == "hi"
    assert seen["body"]["max_tokens"] == 100


@run_async
async def test_gemini_wire_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "answer"}]}}],
                                         "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 3}})

    text, usage = await providers.complete(kind="google", base="https://generativelanguage.googleapis.com", key="gm",
                                           model="gemini-2.5-pro", system="sys", user="hi", max_tokens=64,
                                           temperature=0.4, transport=httpx.MockTransport(handler))
    assert text == "answer"
    assert usage == {"tokens_in": 5, "tokens_out": 3}
    assert ":generateContent" in seen["url"] and "gemini-2.5-pro" in seen["url"]
    assert seen["body"]["system_instruction"]["parts"][0]["text"] == "sys"
    assert seen["body"]["generationConfig"]["maxOutputTokens"] == 64


@run_async
async def test_openai_compatible_wire_format():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}],
                                         "usage": {"prompt_tokens": 2, "completion_tokens": 1}})

    text, usage = await providers.complete(kind="openai", base="https://api.example.com/v1", key="k",
                                           model="m", system="s", user="u", max_tokens=10, temperature=0.0,
                                           transport=httpx.MockTransport(handler))
    assert (text, usage) == ("ok", {"tokens_in": 2, "tokens_out": 1})
    assert seen["url"].endswith("/chat/completions")
    assert seen["body"]["model"] == "m"


@run_async
async def test_llm_reports_a_native_provider_failure(monkeypatch, tmp_path):
    """A 401 from Anthropic becomes the same readable 502 the UI already knows."""
    from app import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "p.db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "bad")
    main.init_db()
    pf.LLM_TRANSPORT = httpx.MockTransport(lambda r: httpx.Response(401, json={"error": {"message": "nope"}}))
    try:
        with pytest.raises(Exception) as exc:
            await pf.llm("sys", "user", "anthropic:claude-opus-4-7", {"kind": "test"})
        assert "rejected the API key" in str(exc.value)
    finally:
        pf.LLM_TRANSPORT = None
