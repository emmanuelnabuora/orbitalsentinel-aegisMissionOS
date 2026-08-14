# Phase 7 — Threat Intelligence engine

## Delivered (replaces the MVP placeholder)
- **Indicator store** (`threat_indicators`), unique by (type, value), with
  category, severity, confidence, source, active flag, first/last seen.
- **Feeds**: curated (zero-dependency) + generic JSON with field mapping.
  `POST /threat-intel/ingest` upserts from all configured providers.
- **Correlation**: `POST /threat-intel/correlate` matches active indicators
  against asset attributes and raises linked `ThreatIntel` alerts into the
  standard pipeline. Idempotent.
- **Read surface**: `/summary`, `/indicators` (filter + search), `/matches`,
  plus manual `POST /indicators`.
- **UI**: full Threat Intelligence page — ingest/correlate actions, live
  summary tiles, an "observed on our assets" table linking to the raised
  alerts, and the filterable indicator feed.
- **SentinelAI**: new threat-intel intent ("who is targeting us?").

## Verified
- 52/52 tests on sqlite **and** PostgreSQL 16 (7 new: ingest idempotency,
  correlation→alert, correlation idempotency, clean-asset negative, RBAC,
  manual registration+search, JSON-feed field mapping).
- Migration up/down/up on Postgres (new tables → no populated-data hazard).
- Live HTTP E2E on Postgres+Redis: 6 indicators ingested, 1 correlated to a
  seeded tainted asset, 1 ThreatIntel alert in the pipeline, idempotent
  re-correlate, SentinelAI intent answering from live data.
- Frontend strict TS build clean.

## Remaining placeholder
Reports is now the only stubbed module.
