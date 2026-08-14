# ADR-0019: SentinelAI Live Provider

Status: Accepted — 2026-07-28

## Decisions

1. **Key-gated activation, config-driven.** `ANTHROPIC_API_KEY` present
   (Secrets Manager in deployment, ADR-0007 pattern) -> AnthropicProvider;
   absent -> deterministic rules engine. No code path changes between
   modes; the same grounded context flows to both.
2. **Pinned, versioned model string** (`claude-sonnet-5` default),
   overridable via `AEGIS_SENTINEL_MODEL` — never alias strings, per
   Anthropic's production guidance, so model upgrades are intentional.
3. **Retry policy mirrors ingestion clients**: capped exponential
   backoff on 429/5xx/transport; 4xx (bad key, bad request) fails fast.
   Injectable httpx client keeps tests hermetic — no live calls in CI.
4. **Fail-open in the engine**: on ProviderError, the deterministic
   draft ships and the provider tag records the degradation
   (`… (degraded->rules)`). A model-provider outage never 500s an
   analyst's workflow.
5. **Grounding boundary preserved**: the provider receives the
   engine-built draft and system prompt only — platform data is
   summarized before it leaves the process; credentials and raw secrets
   never enter prompts.
6. **`GET /sentinel/status`** exposes provider/live/model for the UI
   badge, so demo audiences can see which mode is running.

## Consequences

- Activation is pure ops: put the key in Secrets Manager, restart —
  zero deploys. Removing the key downgrades identically.
- 7 new tests; suite 138 green; zero migrations.


## Addendum — chat() fail-open gap (found via live testing)

`chat()` was missing the same `try/except ProviderError` that `analyze()`
had — a live-provider failure crashed the request instead of degrading.
Fixed to match; both entry points now share identical failure behavior.
Regression-tested at both the service and HTTP-endpoint level.
