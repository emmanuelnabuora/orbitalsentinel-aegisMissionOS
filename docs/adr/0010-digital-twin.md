# ADR-0010: Digital Twin — read-only what-if simulation

## Status
Accepted — Phase 9.

## Context
MissionIQ scores *current* reality. Operators also need to ask about
*hypothetical* futures — "if our primary ground station fails, does any mission
cross into at-risk?" — before it happens, and without touching production data.

## Decisions

### 1. One scoring core, two callers
The assurance math lives in `services/scoring.py` as a pure function over plain
values (`score_mission`). MissionIQ feeds it live DB state; the Digital Twin
feeds it a perturbed in-memory projection. Because both call the identical
function, an empty scenario is provably a no-op: projected average == baseline
average. This "parity" property is asserted in the test suite and was confirmed
live (delta 0 on an empty scenario).

### 2. The projection is read-only
`simulate()` snapshots mission/asset/alert state into local dataclasses, deep-
copies them, and mutates only the copy. No `UPDATE` ever touches an asset. The
decisive live check: after forcing a critical asset offline in simulation, the
real asset is still operational and the live mission score is unchanged. The
twin cannot cause an incident.

### 3. Perturbation vocabulary
Four kinds, enough to express the scenarios operators care about:
`set_status` (explicit status), `offline` (shorthand for total outage),
`add_alerts` (magnitude open alerts), `remove_asset` (total loss — the asset
drops out of every mission it supports). Scenarios are ephemeral: a scenario is
named for the report but nothing is persisted. Referenced assets are validated
up front so a typo'd scenario fails 404 rather than silently scoring nothing.

### 4. Impact framing over raw numbers
The result leads with what a commander needs: fleet average delta, which
missions cross a health threshold, which are newly at-risk (ranked worst-first),
and a grounded one-paragraph summary — plus the per-asset before/after table for
detail.

## Consequences
- **Saved-scenario library (Phase 10):** scenarios are now persisted on a
  `scenarios` table and replayable via `/digital-twin/scenarios/{id}/run`,
  which drives the identical `simulate()` path — a saved run reproduces the
  ad-hoc projection exactly (asserted in tests and confirmed live). This was
  the future increment noted here; the engine was unchanged, as predicted.
- The v1 model is direct-effect: a perturbed asset affects the missions that
  depend on it. Multi-tier *asset-to-asset* dependency cascade (an offline
  upstream degrading downstream assets) is a natural next extension — the
  dependency edges already exist in the model to support it.
