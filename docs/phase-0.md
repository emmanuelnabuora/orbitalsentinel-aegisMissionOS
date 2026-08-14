# Phase 0 — Foundation

## Delivered
- Monorepo layout (apps / packages / infrastructure / database / ai / docs)
- Docker Compose: Postgres 16, Redis 7, Qdrant, API container (non-root)
- FastAPI skeleton: app factory, typed settings, structured logging,
  request-ID + security-header middleware, health/readiness endpoints,
  security primitives (Argon2id, JWT issue/verify), async SQLAlchemy +
  Alembic wired
- React 18 + TS (strict) + Vite + Tailwind shell with OrbitalSentinel
  design tokens and a typed API client stub
- CI: ruff lint + format check, pytest, tsc + Vite build, Docker image build
- ADRs 0001–0002, architecture doc, design-language v0

## Verified
- `ruff check` — clean
- `pytest` — 8/8 passing (health, headers, request-ID propagation, honest
  readiness degradation, password + token round-trips, tamper/issuer rejection)
- `tsc -b && vite build` — clean

## Next
Phase 1: core domain model (assets, missions, dependencies) + auth service
(users, RBAC, refresh rotation, audit log).
