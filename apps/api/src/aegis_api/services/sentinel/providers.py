"""SentinelAI provider abstraction (Phase 19: live Anthropic provider).

`RuleBasedProvider` is deterministic and data-grounded — it always works,
needs no keys, and every statement traces to platform data (Explainable
AI). `AnthropicProvider` upgrades generation quality when an API key is
configured; it receives the same grounded context, never raw credentials
or secrets.

Fail-open (ADR-0004 lineage): a live-provider failure degrades to the
rule-based draft — SentinelAI never 500s because an upstream model
call did.

Model strings are versioned and pinned (never aliases) per Anthropic's
production guidance; override per environment via AEGIS_SENTINEL_MODEL.
"""

from __future__ import annotations

import asyncio

import httpx

from aegis_api.core.config import get_settings
from aegis_api.core.logging import get_logger

log = get_logger("aegis.sentinel")

ANTHROPIC_API = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5"


class ProviderError(Exception):
    """Live provider unreachable/failed after retries."""


class RuleBasedProvider:
    name = "sentinel-rules-v1"
    live = False

    async def complete(self, system: str, user: str) -> str:  # noqa: ARG002
        # Rule-based provider does not free-generate; callers use the
        # structured builders in engine.py. This exists to satisfy the
        # protocol for chat fallback.
        return user


class AnthropicProvider:
    live = True

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1000,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
    ):
        self.model = model
        self.name = f"anthropic:{model}"
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            base_url=ANTHROPIC_API,
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )

    async def aclose(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    async def complete(self, system: str, user: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.post(
                    "/v1/messages",
                    json={
                        "model": self.model,
                        "max_tokens": self._max_tokens,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return "".join(
                    b.get("text", "")
                    for b in data.get("content", [])
                    if b.get("type") == "text"
                )
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                last_exc = exc
                # 4xx other than 429 (bad key, bad request): not retryable.
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    break
                await asyncio.sleep(self._backoff_base_s * (2**attempt))
        log.warning("sentinel_provider_error", model=self.model, error=str(last_exc))
        raise ProviderError(str(last_exc)) from last_exc


def get_provider() -> RuleBasedProvider | AnthropicProvider:
    settings = get_settings()
    api_key = getattr(settings, "anthropic_api_key", None)
    if api_key:
        return AnthropicProvider(
            api_key,
            model=getattr(settings, "sentinel_model", DEFAULT_MODEL),
            max_tokens=getattr(settings, "sentinel_max_tokens", 1000),
        )
    return RuleBasedProvider()
