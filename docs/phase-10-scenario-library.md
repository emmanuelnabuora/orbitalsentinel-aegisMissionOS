# Phase 10 — Saved-scenario library

## Delivered
- **Persistence** (`scenarios` table): named perturbation sets with description,
  author, and `last_run_at`. Scenarios store perturbations as JSON that
  re-validates into `Perturbation` on run.
- **API**: `GET/POST /digital-twin/scenarios`, `GET /scenarios/{id}`,
  `POST /scenarios/{id}/run`, `DELETE /scenarios/{id}`.
- **Replay parity**: running a saved scenario drives the same read-only
  `simulate()` path as an ad-hoc call — a saved run reproduces the ad-hoc
  projection byte-for-byte. Running stamps `last_run_at`.
- **UI**: the Digital Twin page gains a Save button and a scenario-library
  panel (run / delete per scenario) beside the builder.
- RBAC: create/run/delete require OPERATOR/ANALYST; the library is readable by
  any authed user. All mutations audited.

## Why
An ops team targeting DoD/Space Force builds a *playbook* of failure cases
("primary ground station loss", "northern corridor jamming") and replays them
after every fleet change — not a one-off calculation. The engine already
supported the math; this adds the durable library around it.

## Verified
- 74/74 tests on sqlite **and** PostgreSQL 16 (6 new: CRUD, replay parity vs
  ad-hoc simulate, last_run stamping, multi-perturbation round-trip, RBAC).
- Migration up/down/up on Postgres (new table).
- Live HTTP E2E on Postgres+Redis: save → list → run (parity with ad-hoc,
  projected 44 / delta -46) → last_run stamped → **real data unchanged** →
  delete (204 then 404).
- Frontend strict TS build clean.
