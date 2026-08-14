# Phase 9 — Digital Twin

## Delivered
- **What-if simulation**: `POST /digital-twin/simulate` applies a scenario's
  perturbations to a read-only projection of live fleet state and rescores every
  mission through the same core MissionIQ uses.
- **Perturbations**: set_status, offline, add_alerts (magnitude), remove_asset.
- **Impact result**: baseline vs projected fleet average, per-mission deltas
  (ranked worst-first) with health-threshold crossings, newly-at-risk missions,
  per-asset before/after table, and a grounded narrative summary.
- **UI**: Digital Twin page (build a scenario asset-by-asset, run it, read the
  impact) — now wired into the sidebar (after MissionIQ) and router. It had been
  built in an earlier phase but left unrouted; this phase connected it.
- RBAC: simulation requires OPERATOR/ANALYST; every run is audited.

## Verified
- 68/68 tests on sqlite **and** PostgreSQL 16 (8 Digital Twin: score parity on
  empty scenario, offline impact, threshold crossing, remove-asset, alert
  injection, 404 on unknown asset, RBAC).
- Live HTTP E2E on Postgres+Redis: empty scenario delta 0; forcing the critical
  SENTRY-7 offline drove OVERWATCH-ALPHA 90→44 (assured→at-risk, flagged);
  remove-asset set the removed flag; and — the key property — **live data was
  unchanged** after every simulation.
- Frontend strict TS build clean.

## Note on scope
The engine, schema, router, and page pre-existed from earlier work; this phase
restored the schema contract, confirmed correctness end-to-end on both dialects,
and closed the one real gap: the page was unreachable (no nav item / route).
