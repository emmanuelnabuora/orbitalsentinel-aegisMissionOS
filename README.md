# OrbitalSentinel — AEGIS MissionOS

AI-native mission assurance platform for mission-critical infrastructure
across Earth and space.

## Repository layout

```
apps/api            FastAPI service (Python 3.12, SQLAlchemy 2, Alembic)
apps/web            React 18 + TypeScript + Vite + Tailwind
packages/           Shared configs and (soon) UI kit + typed API client
infrastructure/     Terraform (AWS) — deployment phase
database/init/      One-time Postgres extensions (schema lives in Alembic)
ai/                 SentinelAI — Phase 3
docs/               Architecture, ADRs, design language
```

## Quick start

```bash
cp .env.example .env            # then set AEGIS_SECRET_KEY (openssl rand -hex 32)
make up                         # postgres + redis + qdrant
cd apps/api && pip install -e ".[dev]" && cd ../..
make migrate
AEGIS_ADMIN_EMAIL=you@example.com AEGIS_ADMIN_PASSWORD='min-12-chars' \
    python apps/api/scripts/seed.py   # demo admin + sample mission
make api                        # http://localhost:8000/docs
cd apps/web && npm install && npm run dev   # http://localhost:5173
```

## Verification

```bash
make lint    # ruff + tsc
make test    # pytest
```

Every commit must leave `make lint && make test` green — CI enforces it.
