"""Resilient async HTTP base for ingestion clients.

Upstream sources are best-effort enrichment: transient failures retry
with capped exponential backoff; persistent failures raise
SourceUnavailable, which callers log and swallow (fail-open, ADR-0011).
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from aegis_api.core.logging import get_logger

log = get_logger("aegis.ingestion")

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
USER_AGENT = "AEGIS-MissionOS/1.0 (OrbitalSentinel ingestion)"


class SourceUnavailable(Exception):
    """Upstream source unreachable after retries."""


class BaseSourceClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
        backoff_base_s: float = 0.5,
    ) -> None:
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=DEFAULT_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s

    async def aclose(self) -> None:
        if not self._external_client:
            await self._client.aclose()

    async def _get_json(self, path: str, params: dict | None = None) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = await self._client.get(path, params=params)
                resp.raise_for_status()
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                last_exc = exc
                # Non-transient 4xx (except 429): do not retry.
                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    break
                await asyncio.sleep(self._backoff_base_s * (2**attempt))
        log.warning("source_unavailable", path=path, error=str(last_exc))
        raise SourceUnavailable(str(last_exc)) from last_exc
