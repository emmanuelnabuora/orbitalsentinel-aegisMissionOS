# ADR-0011: Live Data Ingestion (Celestrak + NOAA SWPC)

Status: Accepted — 2026-07-27

## Context

AEGIS has run on deterministic seed data through Phase 10. Customer
demos and QuantumShield realism require live orbital and space-weather
inputs. The authoritative DoD sources (UDL, Space-Track CDMs) require
sponsorship or role approval, so the first live milestone uses the two
zero-friction public sources: the Celestrak GP catalog and NOAA SWPC.

## Decision

1. **In-process asyncio scheduler**, not a separate worker service.
   Consistent with the modular monolith (ADR-0001); polling four JSON
   endpoints does not justify new infrastructure. Loops start from the
   FastAPI lifespan only when `data_source == "live"`.
2. **Ports at the module boundary.** Ingestion depends on two Protocols
   — `AlertSink` and `EphemerisSink` — with DB-backed implementations
   in `sinks.py`. Ingestion never reaches into other services' logic;
   the alerts table remains the single alert store.
3. **Fail-open.** Source outages log and skip. The platform never
   degrades because an enrichment feed is down; last-known data serves.
4. **Natural-key deduplication.** `alerts.dedupe_key` (nullable,
   unique-indexed). Kp/solar-wind drafts key on a UTC 3-hour synoptic
   bucket (one alert per storm period); SWPC bulletins key on
   `(product_id, issue_datetime)`. Sink submit is idempotent.
5. **Severity policy fixed in code, not config**, following the NOAA
   G-scale: Kp ≥ 7 → critical, Kp ≥ 5 → high; wind ≥ 800 km/s or
   Bz ≤ −15 nT → critical, ≥ 600 km/s or Bz ≤ −10 nT → high;
   bulletins WARNING/ALERT → medium, WATCH → low. Unit-tested.
6. **Separate `asset_ephemeris` table** keyed on `norad_cat_id` rather
   than columns on `assets` (expand-then-contract, ADR-0005 style):
   catalog objects vastly outnumber managed assets, and a later
   `assets.norad_cat_id` linkage joins cleanly without schema churn.
7. **Polite cadences.** Celestrak GP every 6 h; SWPC products every
   2–5 min. Dataclass-configurable.

## Consequences

- Space-Track and UDL clients later drop in as additional
  `BaseSourceClient` subclasses behind the same sinks; `GPRecord` is
  OMM-shaped, mirroring their data models.
- Multi-instance deployments double-poll. Acceptable now (dedupe makes
  it harmless); if instance count grows, move loops to a singleton
  scheduled task or add a Redis leader lock (Redis already in stack).
- Tests use `httpx.MockTransport` with realistic payload fixtures; CI
  needs no network egress. 17 tests added; full suite remains green.
