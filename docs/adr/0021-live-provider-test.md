# ADR-0021: Opt-In Live Provider Integration Test

Status: Accepted — 2026-07-28

## Context

Phase 19 shipped `AnthropicProvider` with full unit-test coverage
against a mocked transport — correct for CI (fast, free, deterministic)
but it never proves a real deployed key, model string, and network path
actually work together. That gap surfaced directly: a real key tested
by hand via curl revealed a billing issue no unit test could catch.

## Decisions

1. **Double opt-in, not a single flag.** Both `AEGIS_RUN_LIVE_TESTS=1`
   and `ANTHROPIC_API_KEY` must be present. A key alone (e.g. exported
   for local `uvicorn` work) must not silently make `pytest` spend
   money or require connectivity — that would be a footgun for anyone
   who simply has the variable set in their shell profile.
2. **Skip at collection, not per-test.** `pytestmark` at module level
   means the whole file — fixtures included — is skipped when the gate
   isn't satisfied, not just individual assertions. Default `pytest`
   output shows `2 skipped`, not `2 passed (mocked)`, so the distinction
   stays visible rather than being hidden by a green run.
3. **Separate file, separate marker.** `tests/test_live_sentinel.py` is
   excludable by path (`--ignore`) as well as by marker (`-m`), and
   `make test-live` is a distinct target from `make test` — the person
   running tests always has to ask for the network explicitly.
4. **Failures diagnose, not just fail.** `pytest.fail()` with the
   caught `ProviderError` message plus a short list of common causes
   (credit balance, revoked key, bad model string) — the same triage
   a person would otherwise do by hand.
5. **Status-endpoint test clears the settings cache.** `get_settings`
   is `@lru_cache`d process-wide; the live test forces a fresh read so
   a key exported only for this test run is actually picked up, and
   clears it again in `finally` so no live settings object leaks into
   later tests in the same process.

## Consequences

- CI and `make test` are unaffected — 145 passed, 2 skipped, zero
  network, exactly as before this phase.
- The harness was verified against both an invalid key (clean 401
  diagnostic, no crash) and the double-opt-in gate itself (confirmed
  skip-at-collection).
