# Phase 11 — Live Data Ingestion (Celestrak + NOAA SWPC)

First live data flowing into AEGIS: real orbital element sets and real
space weather, with zero credentials required. Gated behind
`AEGIS_DATA_SOURCE=live`; the default `seed` changes nothing, so this
phase is safe to deploy immediately and flip per environment.

## What shipped

**Source clients** (`aegis_api/services/ingestion/clients/`)
- `CelestrakClient` — GP/OMM catalog by group, NORAD number, or name.
  Handles Celestrak's plain-string "No GP data found" responses.
- `SwpcClient` — 1-minute planetary Kp, solar-wind speed + IMF (Bt/Bz),
  and issued bulletins. Normalizes SWPC's inconsistent timestamp formats.
- `BaseSourceClient` — shared httpx async base: 10 s timeout, capped
  exponential-backoff retries on 5xx/429/transport errors, no retry on
  other 4xx, injectable `httpx.AsyncClient` for hermetic tests.

**Normalization + policy** (`service.py`)
- NOAA G-scale mapped to `AlertSeverity`: Kp ≥ 7 → critical, Kp ≥ 5 →
  high; solar wind ≥ 800 km/s or Bz ≤ −15 nT → critical, ≥ 600 km/s or
  Bz ≤ −10 nT → high; bulletins WARNING/ALERT → medium, WATCH → low.
- Deduplication by natural key: Kp/wind alerts key on a UTC 3-hour
  synoptic bucket (one alert per storm period, not one per poll);
  bulletins key on `(product_id, issue_datetime)`.
- Fail-open: source outages log and skip; the platform serves on.

**Persistence**
- `alerts.dedupe_key` (nullable, unique-indexed) — idempotent ingestion
  writes through the existing alerts table.
- `asset_ephemeris` — latest OMM elements per NORAD object, upserted on
  each catalog refresh. Standalone table (expand-then-contract); assets
  can gain a NORAD linkage later without touching this write path.
- Migration `b2c4e6a81f00`.

**Scheduler** (`scheduler.py`, wired in `main.py` lifespan)
- In-process asyncio loops: solar wind every 2 min, Kp and bulletins
  every 5 min, Celestrak catalog every 6 h (element sets change at most
  a few times daily; Celestrak throttles abusers).
- Started only when `data_source == "live"`; clean cancellation on
  shutdown.

## Configuration

```
AEGIS_DATA_SOURCE=seed|live       # default seed
AEGIS_INGEST_CATALOG_GROUP=active # any Celestrak group, e.g. starlink
```

No secrets: both sources are public and unauthenticated. When
Space-Track lands, its credentials go to Secrets Manager like all others.

## Verification

```
cd apps/api && python -m pytest tests/test_ingestion.py -q   # 17 tests, no network
AEGIS_DATA_SOURCE=live make api                              # watch aegis.ingestion logs
```

First live signals: a solar-wind poll within ~2 min of boot; a Kp alert
only if Kp ≥ 5 right now (check swpc.noaa.gov); catalog refresh at +5 s
jitter, then every 6 h.

## Deployment note

ECS tasks reach celestrak.org and services.swpc.noaa.gov via the NAT
gateways — egress is open outbound, no security-group change. Multiple
API instances would double-poll; dedupe makes that harmless today, and
ADR-0011 records the leader-lock upgrade path if instance count grows.

## Next data milestones (by friction)

1. `ANTHROPIC_API_KEY` in Secrets Manager → SentinelAI live provider
2. Space-Track client (registration + rate limits; same client pattern)
3. Celestrak SOCRATES conjunctions → Incidents pipeline
4. UDL (requires customer sponsorship)
