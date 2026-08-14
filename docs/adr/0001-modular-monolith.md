# ADR-0001: Modular monolith in a monorepo

Status: accepted · Date: 2026-07-09

## Context
The platform spec lists 15 product modules. A microservice per module would
mean ~15 deployables before a single customer demo, with all the operational
drag that implies for a founding team.

## Decision
One FastAPI service, strict internal module boundaries (feature packages with
their own routers/services/repositories), one Postgres database with
Alembic-owned schema. Monorepo so API, web, infra, and AI evolve in lockstep
with atomic cross-cutting changes.

## Consequences
- Fast iteration and one CI pipeline now; extraction path preserved because
  modules already communicate through service interfaces, not shared tables.
- The discipline burden shifts to code review: cross-module imports outside
  service interfaces are rejected.
