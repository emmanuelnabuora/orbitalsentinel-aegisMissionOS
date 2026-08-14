# ADR-0022: Space-Track.org Integration (Session Auth, CDMs)

Status: Accepted — 2026-07-29

## Context

Space-Track is the authoritative U.S. source for orbital data and
Conjunction Data Messages (CDMs) — the natural extension of the
Celestrak/SOCRATES ingestion from Phases 6/11/18, and the next data
milestone flagged since ADR-0018.

Its integration shape differs from every other source in this codebase
in one important way: **there is no API key.** Authentication is your
registered account's username and password, exchanged for a session
cookie.

## Decisions

1. **Session-cookie auth, not `BaseSourceClient`.** `SpaceTrackClient`
   is a standalone class (not a `BaseSourceClient` subclass) because
   its failure mode is different: a 401 mid-session means "re-login and
   retry," not "give up." It shares `SourceUnavailable` as its failure
   type so `IngestionService` treats it identically to every other
   source (fail-open, no special-casing).
2. **Credentials are optional settings**, matching the
   `ANTHROPIC_API_KEY` pattern (Phase 19): `SPACETRACK_USERNAME` /
   `SPACETRACK_PASSWORD`, no `AEGIS_` prefix (third-party credential,
   not platform config). Ingestion runs fully without them — Celestrak
   and SOCRATES remain the free, keyless baseline.
3. **CDM operator-scoping is documented, not hidden.** Space-Track's
   `cdm` class returns messages addressed to an organization's *own
   registered spacecraft* — it is not a general public feed like
   SOCRATES. An account with no registered satellites will correctly
   see an empty result set. This is called out in the client's module
   docstring and tested explicitly
   (`test_operator_gated_empty_result_is_not_an_error`) so it's never
   mistaken for a bug during a demo or a customer deployment.
4. **Shared conjunction pipeline, not a parallel one.** The
   alert-building, severity policy, tracked-asset lookup, and
   escalation logic from Phase 18 (`_process_conjunctions`) is
   extracted into one method used by both `poll_conjunctions` (SOCRATES)
   and the new `poll_cdms` (Space-Track) — only the dedupe-key strategy
   and provenance tag differ per source.
5. **Unit conversion at the parse boundary.** CDM reports
   `MISS_DISTANCE` in meters and `RELATIVE_SPEED` in m/s;
   `ConjunctionRecord` (built around SOCRATES) uses km and km/s.
   `CdmRecord.from_raw()` converts once, at ingestion, so severity
   thresholds and downstream code never need to know which source a
   record came from.
6. **CDM_ID is the dedupe key**, not a derived bucket — unlike SOCRATES
   (no stable per-conjunction identifier), Space-Track provides one
   directly. The two sources' dedupe keys (`spacetrack:cdm:*` vs
   `socrates:*`) are namespaced so the same physical conjunction
   reported by both is tracked as two independent alerts, not
   incorrectly merged — different originating systems can carry
   different Pc estimates.
7. **Throttling respected two ways**: batched comma-delimited NORAD-id
   queries for `get_gp_by_catnrs` (never one request per satellite,
   per Space-Track's explicit guidance), and a minimum inter-request
   interval enforced client-side on top of that.

## Consequences

- Cadence set conservatively at 4h for CDM polling.
- 11 new tests; suite at 160 passed / 2 skipped (live-network tests
  unaffected); zero migrations (reuses Alert/Incident/AssetEphemeris).
- `get_gp_by_catnrs` is unused by the scheduler today — a reusable
  capability for when authoritative (vs. Celestrak-mirrored) catalog
  data is needed for specific tracked assets.
