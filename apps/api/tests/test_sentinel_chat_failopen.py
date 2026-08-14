"""Regression tests: SentinelAI chat must fail open (Phase 19 follow-up).

Bug: analyze() caught ProviderError and degraded to the rules draft;
chat() had no such handling, so a live-provider failure (bad model
string, expired key, outage) propagated as an unhandled exception —
surfacing as a 500 to whoever was using the SentinelAI Copilot, exactly
contradicting the documented fail-open guarantee (ADR-0019).

A second, related bug this catches: the pinned default model string
was not a real Anthropic model, so every live call would have failed
this way regardless of how correctly a key was configured.
"""

from __future__ import annotations

from aegis_api.services.sentinel.engine import SentinelService
from aegis_api.services.sentinel.providers import DEFAULT_MODEL, ProviderError


class _FailingProvider:
    """Stands in for a live provider whose API call fails — bad model
    string, revoked key, or a transient outage all look the same here."""

    name = "anthropic:claude-sonnet-5"
    live = True

    async def complete(self, system: str, user: str) -> str:  # noqa: ARG002
        raise ProviderError("simulated: model not found")


def test_default_model_is_a_real_pinned_string():
    """Guards against another placeholder-looking string slipping in.
    Real Anthropic model ids are dash-separated lowercase tokens; this
    doesn't validate against the live API (that's test_live_sentinel.py's
    job) but it does catch an obviously-fabricated string at review time."""
    assert DEFAULT_MODEL == "claude-sonnet-5"
    assert not DEFAULT_MODEL.endswith(("-4-6", "-preview", "-test"))


async def test_chat_fails_open_on_provider_error(db, make_user):
    """The actual bug: chat() must degrade to the rules draft and tag
    the response, never raise, when the live provider fails."""
    from aegis_api.models.enums import Role

    user, _ = await make_user("sentinel.chat.user@orbitalsentinel.io", Role.ANALYST)
    async with db() as session:
        svc = SentinelService(session)
        svc.provider = _FailingProvider()  # simulate the live call failing

        response = await svc.chat("what is our mission assurance?", actor_id=user.id)

    assert response.answer  # deterministic draft still shipped
    assert response.provider == "anthropic:claude-sonnet-5 (degraded->rules)"


async def test_chat_endpoint_never_500s_on_provider_failure(client, admin, monkeypatch):
    """End-to-end: the HTTP path a person actually hits from the
    SentinelAI Copilot page must return 200 even when the configured
    live provider is broken."""
    import aegis_api.services.sentinel.engine as engine_module

    monkeypatch.setattr(engine_module, "get_provider", lambda: _FailingProvider())

    _, headers = admin
    r = await client.post(
        "/api/v1/sentinel/chat", json={"message": "what is our threat level?"}, headers=headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"]
    assert "degraded->rules" in body["provider"]


async def test_chat_unaffected_when_no_live_provider_configured(client, admin, monkeypatch):
    """Sanity check the fix didn't change default (no-key) behavior."""
    import aegis_api.services.sentinel.engine as engine_module
    from aegis_api.services.sentinel.providers import RuleBasedProvider

    monkeypatch.setattr(engine_module, "get_provider", lambda: RuleBasedProvider())

    _, headers = admin
    r = await client.post(
        "/api/v1/sentinel/chat", json={"message": "what is our threat level?"}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["provider"] == "sentinel-rules-v1"
