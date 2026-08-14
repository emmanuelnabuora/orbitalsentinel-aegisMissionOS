# Phase 18 — SOCRATES Conjunctions and Auto-Escalation

## What shipped

- `SocratesClient`: Celestrak SOCRATES close-approach CSV, alias-tolerant
  header matching, configurable path, no auth
- Severity screening (CARA-style): Pc/miss-distance thresholds ->
  CRITICAL / HIGH / MEDIUM alerts with order-normalized dedupe per
  (pair, TCA)
- **Auto-escalation**: a CRITICAL conjunction involving a tracked asset
  (known in `asset_ephemeris`) opens a system incident — `[AUTO]` title,
  no commander, alert linked, timeline seeded — idempotently
- Scheduler loop every 8 h; wired behind `AEGIS_DATA_SOURCE=live` like
  all ingestion

## The demo story this completes

Live catalog lands in `asset_ephemeris` (Phase 6/11) -> SOCRATES
reports a close approach on ISS -> a CRITICAL conjunction alert appears
-> an incident auto-opens in the SOC Command and Incident Response
workspaces -> the responder's queue shows `[AUTO] Conjunction: ISS ×
DEBRIS-A (0.41 km)` with the full TCA/Pc telemetry. End-to-end: public
space data to commanded response, no human in the ingestion loop.

## Verify

```
cd apps/api && python -m pytest tests/test_conjunctions.py -q  # 6 tests
AEGIS_DATA_SOURCE=live uvicorn aegis_api.main:create_app --factory
# conjunction loop fires at +5 s jitter, then every 8 h
```

## Next data milestones

1. Anthropic API key -> SentinelAI live (env slot ready)
2. Space-Track CDM client (reuses ConjunctionRecord + escalation path)
3. UDL (customer sponsorship)
