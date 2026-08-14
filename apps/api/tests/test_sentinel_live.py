"""Phase 19 — SentinelAI live provider."""

from __future__ import annotations

import httpx
import pytest

from aegis_api.core.config import get_settings
from aegis_api.services.sentinel.providers import (
    AnthropicProvider,
    ProviderError,
    RuleBasedProvider,
    get_provider,
)


def _messages_response(text: str) -> dict:
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "model": "claude-sonnet-5",
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def make_provider(handler, **kw) -> AnthropicProvider:
    client = httpx.AsyncClient(
        base_url="https://api.anthropic.com", transport=httpx.MockTransport(handler)
    )
    return AnthropicProvider("test-key", client=client, backoff_base_s=0.0, **kw)


async def test_complete_extracts_text_blocks():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/messages"
        body = request.read().decode()
        assert "claude-sonnet-5" in body and "SentinelAI" in body
        return httpx.Response(200, json=_messages_response("Refined analysis."))

    p = make_provider(handler)
    out = await p.complete("You are SentinelAI.", "draft")
    assert out == "Refined analysis."
    assert p.name == "anthropic:claude-sonnet-5" and p.live


async def test_retry_on_429_then_success():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, json={"error": {"type": "rate_limit_error"}})
        return httpx.Response(200, json=_messages_response("ok"))

    p = make_provider(handler)
    assert await p.complete("s", "u") == "ok"
    assert calls["n"] == 3


async def test_no_retry_on_401_bad_key():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={"error": {"type": "authentication_error"}})

    p = make_provider(handler)
    with pytest.raises(ProviderError):
        await p.complete("s", "u")
    assert calls["n"] == 1


async def test_provider_error_after_5xx_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, json={"error": {"type": "overloaded_error"}})

    p = make_provider(handler)
    with pytest.raises(ProviderError):
        await p.complete("s", "u")


def test_factory_without_key_is_rule_based(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", None, raising=False)
    assert isinstance(get_provider(), RuleBasedProvider)


def test_factory_with_key_is_live(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test", raising=False)
    monkeypatch.setattr(settings, "sentinel_model", "claude-haiku-4-5-20251001", raising=False)
    p = get_provider()
    assert isinstance(p, AnthropicProvider)
    assert p.name == "anthropic:claude-haiku-4-5-20251001"


async def test_status_endpoint(client, admin):
    _, headers = admin
    r = await client.get("/api/v1/sentinel/status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "sentinel-rules-v1" and body["live"] is False
