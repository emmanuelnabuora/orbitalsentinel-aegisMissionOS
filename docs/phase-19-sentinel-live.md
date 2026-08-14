# Phase 19 — SentinelAI Live

## What shipped

- Production-grade `AnthropicProvider`: settings-driven key
  (`ANTHROPIC_API_KEY`), pinned model (`claude-sonnet-5` default,
  `AEGIS_SENTINEL_MODEL` to override, e.g. `claude-haiku-4-5-20251001` for
  cheap dev), 30 s timeout, capped-backoff retries on 429/5xx, fail-fast on
  auth errors, hermetic tests via injectable transport
- **Fail-open engine**: live-provider failure degrades to the
  deterministic rules draft with a visible provider tag — analyses
  always complete
- `GET /api/v1/sentinel/status` + UI badge on the Copilot page:
  green "Live · claude-sonnet-5" with a key, neutral "Rules engine"
  without

## Activation (pure ops, no deploy)

Local:
```
export ANTHROPIC_API_KEY=sk-ant-...      # from console.anthropic.com
uvicorn aegis_api.main:create_app --factory
```

Deployment: store the key in AWS Secrets Manager, inject as
`ANTHROPIC_API_KEY` in the task definition, restart the service. The
Sentinel badge flips to Live. Remove the key to downgrade identically.

Cost control: set `AEGIS_SENTINEL_MODEL=claude-haiku-4-5-20251001` in
non-production environments.

## Remaining data milestones

1. Space-Track CDM client (registration; reuses conjunction path)
2. UDL (customer sponsorship)


## Addendum (Phase 19.1) — two bugs found and fixed

A real-world test with a live key surfaced two issues, both fixed and
regression-tested (`tests/test_sentinel_chat_failopen.py`):

1. **The pinned model string was not a real model.** `claude-sonnet-4-6`
   does not exist; every live call would 404 regardless of how correctly
   a key was configured. Corrected to `claude-sonnet-5`
   (cheap-tier override: `claude-haiku-4-5-20251001`).
2. **`chat()` did not fail open.** `analyze()` caught `ProviderError`
   and degraded to the rules draft; `chat()` — the path the SentinelAI
   Copilot page actually calls — had no such handling, so a live-provider
   failure surfaced as an unhandled exception (500) instead of a graceful
   degraded response. This directly contradicted ADR-0019's stated
   guarantee and is why "SentinelAI didn't go live" even after the model
   fix alone would not have been enough. Both methods now behave
   identically on failure.
