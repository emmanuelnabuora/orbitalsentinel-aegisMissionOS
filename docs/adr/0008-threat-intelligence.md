# ADR-0008: Threat Intelligence — indicators, feeds, and correlation into alerts

## Status
Accepted — Phase 7.

## Context
The MVP shipped a Threat Intelligence placeholder promising "IOC ingestion that
integrates with the Alerts pipeline." This delivers exactly that: threat intel
must not be a parallel silo operators check separately — a match on our
infrastructure is an operational event that belongs in the triage queue they
already work.

## Decisions

### 1. Indicators identified by (type, value); feeds upsert
`ThreatIndicator` has a unique constraint on `(indicator_type, value)`.
Re-ingesting the same IOC refreshes `last_seen`, raises `confidence` to the max
seen, and reactivates it — never duplicates. This makes ingestion safe to run
on any schedule.

### 2. Pluggable feed providers
A `FeedProvider` protocol with two implementations: `CuratedFeedProvider`
(a vetted starter set, so the module works fully in air-gapped evaluation with
no external calls) and `JSONFeedProvider` (any HTTP JSON feed via a declarative
field mapping — OTX, abuse.ch, MISP exports). The HTTP transport is injectable,
so feed logic is tested hermetically. Demo/curated values use reserved ranges
(RFC 5737, `.invalid`) so they can never collide with real infrastructure.

### 3. Correlation raises real alerts, idempotently
The engine flattens each asset's `attributes` JSON to string leaves and matches
them against active indicators. A hit writes a `ThreatMatch` **and** an `Alert`
with source `ThreatIntel`, severity inherited from the indicator, linked to the
asset — a first-class citizen of the existing pipeline. A unique
`(indicator, asset)` constraint plus a pre-loaded set of existing pairs makes
correlation idempotent: re-running raises nothing new.

### 4. RBAC
Reading intel is available to any authenticated user; ingest/correlate/register
require OPERATOR or ANALYST. Every mutation is audited.

## Consequences
- Attribute-equality matching is deliberate and explainable for v1. Fuzzy /
  CIDR / substring matching and MITRE ATT&CK technique mapping are future work
  on the same store.
- SentinelAI gained a threat-intel intent, so the copilot answers "who is
  targeting us?" from the same live data.

## Test-suite lesson
A feed test passed a random `actor_id` to an audited operation. sqlite (FKs off
by default) accepted it; PostgreSQL rejected it against the audit→users FK.
Fixed by persisting a real actor. Reinforces why the suite runs on both
dialects — the sqlite-only pass was hiding a real integrity assumption.
