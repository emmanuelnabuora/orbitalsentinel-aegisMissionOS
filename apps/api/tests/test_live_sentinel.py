"""Opt-in live integration test for the SentinelAI Anthropic provider.

This is the ONLY test in the suite that touches the real network. It is
double-gated so it can never run by accident:

  1. AEGIS_RUN_LIVE_TESTS=1   — explicit opt-in, separate from just
     having a key in the environment (a dev might export a key for
     local `uvicorn` work without wanting every `pytest` run to spend
     money or need connectivity).
  2. ANTHROPIC_API_KEY set    — the actual credential.

Both absent (the default: CI, `make test`, a bare `pytest`) -> the
whole module is skipped at collection time, not just individual tests,
so no fixtures spin up and no network is attempted.

Run it explicitly:
    AEGIS_RUN_LIVE_TESTS=1 ANTHROPIC_API_KEY=sk-ant-... \\
        python -m pytest tests/test_live_sentinel.py -v -s

Uses claude-haiku-4-5-20251001 by default (cheap) — override with
AEGIS_LIVE_TEST_MODEL if you want to check a specific model string.
"""

from __future__ import annotations

import os

import pytest

from aegis_api.core.config import get_settings
from aegis_api.services.sentinel.providers import AnthropicProvider, ProviderError

RUN_LIVE = os.getenv("AEGIS_RUN_LIVE_TESTS") == "1"
API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = os.getenv("AEGIS_LIVE_TEST_MODEL", "claude-haiku-4-5-20251001")

pytestmark = pytest.mark.skipif(
    not (RUN_LIVE and API_KEY),
    reason=(
        "live provider test: set AEGIS_RUN_LIVE_TESTS=1 and ANTHROPIC_API_KEY "
        "to run (see module docstring)"
    ),
)


@pytest.mark.live
async def test_live_provider_completes_a_real_request():
    """Proves the deployed credential and model string actually work —
    the same check a person would otherwise do by hand with curl."""
    provider = AnthropicProvider(API_KEY, model=MODEL, max_tokens=30)
    try:
        text = await provider.complete(
            "You are a terse test harness.",
            "Reply with exactly: AEGIS SentinelAI live test OK",
        )
    except ProviderError as exc:
        pytest.fail(
            f"Live Anthropic call failed ({MODEL}): {exc}\n"
            "Common causes: no credit balance, revoked/invalid key, or an "
            "unrecognized model string."
        )
    finally:
        await provider.aclose()

    assert text.strip(), "Live provider returned an empty response"
    print(f"\n[live] model={MODEL} response={text.strip()!r}")


@pytest.mark.live
async def test_live_status_endpoint_reports_live(client, admin):
    """End-to-end: with a real key in the environment, the factory this
    endpoint calls should select AnthropicProvider, not the rule-based
    fallback — the same badge flip a person sees in the SentinelAI UI."""
    _, headers = admin
    get_settings.cache_clear()  # force a fresh read of ANTHROPIC_API_KEY
    try:
        r = await client.get("/api/v1/sentinel/status", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["live"] is True
        assert body["provider"].startswith("anthropic:")
    finally:
        get_settings.cache_clear()  # don't leak a live settings object
