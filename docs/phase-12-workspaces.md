# Phase 12 — Workspaces, Role Personas, and Programmatic Access

## What shipped

**Tenancy (backend)**
- `workspaces` / `workspace_members` tables; per-workspace roles
- `X-Workspace: <slug>` header scopes assets, missions, alerts, and
  incidents (nullable expand phase; unscoped legacy view preserved)
- Generic 404 for unknown-slug and not-a-member alike

**Roles**
- New: `soc_manager`, `executive`, `auditor` (string-backed, ALTER-free)
- Read-only audit endpoint `GET /api/v1/audit` for auditors and admins

**Access lifecycle**
- Workspace + platform invites: SHA-256 tokens, burned on use, one
  generic error for every redemption failure mode
- Service accounts (OPERATOR-capped, unusable password) and API keys
  (`aegis_sk_{prefix}_{secret}`, hash-only storage, `X-API-Key` auth)
- Lockout guards: no self-demotion, no last-admin removal

**Seven role workspaces (frontend)**
- Platform Administrator, Organization Administrator, Mission Operator,
  Security Analyst, SOC Manager, Executive Dashboard, Auditor
- Role-aware routing: "/" lands each user on their home workspace;
  nav filtered per persona; workspace switcher in the header drives the
  `X-Workspace` header on every API call

## Try it

```
cd apps/api
alembic upgrade head
python scripts/seed_team.py     # team + one demo user per persona (creds printed once)
uvicorn aegis_api.main:create_app --factory

cd ../web && npm run dev
```

Log in as any persona to see its workspace; e.g. demo.socmanager@…
lands on SOC Command, demo.auditor@… on Audit & Compliance.

## Follow-ups

- Contract step: require workspace on writes once data is assigned
- Route ingestion alerts into a workspace (currently platform-level)
- Org-admin UI for API key management (endpoints exist; page next)
