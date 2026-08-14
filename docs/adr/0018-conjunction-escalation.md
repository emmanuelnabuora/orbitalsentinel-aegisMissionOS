# ADR-0018: Conjunction Ingestion and Alert-to-Incident Escalation

Status: Accepted — 2026-07-28

## Decisions

1. **SOCRATES CSV via an alias-tolerant parser.** CelesTrak has renamed
   exports before; the client matches documented column names
   case-insensitively through an alias table and degrades to empty (with
   a log) on unrecognized headers rather than erroring. The export path
   is constructor-configurable.
2. **Screening thresholds follow NASA CARA practice, simplified**:
   Pc >= 1e-4 or miss < 1 km -> CRITICAL; Pc >= 1e-5 or miss < 5 km ->
   HIGH; Pc >= 1e-7 -> MEDIUM; else ignored. Fixed in code, unit-tested.
3. **Escalation is a port** (`IncidentSink.escalate`), rule evaluated in
   the ingestion service: CRITICAL conjunction ∧ involves a tracked
   asset (present in `asset_ephemeris`) -> auto-open an incident.
   Escalation is idempotent through the alert's dedupe_key: an alert
   already linked to an incident is never escalated twice.
4. **System incidents have no commander** (`commander_id NULL`), titled
   `[AUTO] …`, opened with `created` + `alert_linked` events attributed
   to no actor. A SOC manager claims ownership in the UI — automation
   proposes, humans command.
5. **Conjunction dedupe key is order-normalized**
   (`socrates:{min}:{max}:{TCA-minute}`) so the same pair reported in
   either order is one event.
6. Cadence 8 h (SOCRATES updates ~3x/day). No schema changes — the
   phase composes entirely from Phase 6/11 structures.

## Consequences

- Space-Track CDMs later reuse `ConjunctionRecord` + the same
  escalation path; only a client is needed.
- 6 new tests; suite 131 green; zero migrations.
