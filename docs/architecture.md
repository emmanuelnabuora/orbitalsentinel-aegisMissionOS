# Architecture — Phase 0 baseline

## Shape

Monorepo, modular monolith to start. One FastAPI service exposes a versioned
REST API (`/api/v1`); the React SPA consumes it through a Vite dev proxy
locally and an ALB path route in AWS. Modules (Alerts, Missions, Assets,
SentinelAI…) are packages inside `aegis_api`, each owning its routers,
services, repositories, and models. We split services out only when a module
earns it (independent scaling or isolation requirements), not before.

## Layering (Clean Architecture)

```
api/        HTTP routers — validation, auth, serialization. No business logic.
services/   Use cases. Orchestrate repositories, enforce invariants.
repositories/  All persistence. Only layer that touches SQLAlchemy sessions.
models/     ORM entities + domain types.
core/       Cross-cutting: config, security, db, logging.
```

Dependencies point inward. Routers never import repositories directly;
everything arrives via FastAPI dependency injection, which keeps each layer
testable in isolation.

## Data stores

- **PostgreSQL 16** — system of record. Schema owned exclusively by Alembic.
- **Redis 7** — caching, rate limiting, later pub/sub for live ops feeds.
- **Qdrant** — vector store for SentinelAI retrieval (Phase 3).

## Security baseline (Phase 0)

- Argon2id password hashing; short-lived JWTs with explicit algorithm
  allow-list, issuer validation, and required-claims enforcement.
- Security headers + request-ID correlation on every response via middleware.
- API docs and OpenAPI endpoint disabled outside local/test.
- Non-root container user; secrets only via environment, validated at boot
  (production refuses to start with a dev secret key).
- CORS restricted to an explicit origin list.

Phase 1 adds the auth service proper: refresh-token rotation, RBAC tables,
and audit logging on every mutating request.

## Observability

Structured logs (structlog): console-rendered locally, JSON in staging/prod
for SIEM ingestion. `request_id` is bound to log context per request and
echoed in the `X-Request-ID` response header. Liveness (`/healthz`) never
touches dependencies; readiness (`/readyz`) checks Postgres and Redis and
returns 503 with per-dependency detail when degraded.
