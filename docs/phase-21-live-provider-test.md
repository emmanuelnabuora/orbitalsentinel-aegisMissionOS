# Phase 21 — Opt-In Live Provider Test

Answers "how do I know the real key actually works?" with an automated
check instead of a manual curl — while keeping every default test run
exactly as fast, free, and network-free as before.

## What shipped

- `tests/test_live_sentinel.py` — two tests, both gated behind
  **`AEGIS_RUN_LIVE_TESTS=1` AND `ANTHROPIC_API_KEY`** being set:
  - `test_live_provider_completes_a_real_request` — makes one real
    completion call against `claude-haiku-4-5` (cheap), fails with a
    clear diagnostic (not a stack trace) if the key/billing/model is
    wrong
  - `test_live_status_endpoint_reports_live` — confirms `GET
    /api/v1/sentinel/status` reports `live: true` when a real key is
    present, i.e. the same badge flip visible in the SentinelAI UI
- `make test-live` — separate from `make test`, so the network path is
  always opt-in
- `live` pytest marker registered (no "unknown marker" warnings)

## Run it

```
export ANTHROPIC_API_KEY=sk-ant-...      # a fresh, rotated key — never one pasted in chat
make test-live
```

Or directly:
```
cd apps/api
AEGIS_RUN_LIVE_TESTS=1 python -m pytest tests/test_live_sentinel.py -v -s
```

## Verify nothing else changed

```
make test   # 145 passed, 2 skipped — the two live tests, cleanly excluded
```

## Security note

This phase does not store, log, or ship any API key. If a key was ever
pasted into a chat, terminal history shared with others, or a
screen-share, rotate it at console.anthropic.com — Settings → API Keys
— regardless of whether it still has a credit balance.
