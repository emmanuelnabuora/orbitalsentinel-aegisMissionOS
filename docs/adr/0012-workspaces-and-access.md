# ADR-0012: Workspaces, Role Model Expansion, and Programmatic Access

Status: Accepted — 2026-07-27

## Context

AEGIS needed (a) a tenancy boundary for multi-organization deployments,
(b) role-specific workspace experiences for seven personas, and (c)
programmatic access for ingestion partners — without breaking the
existing single-tenant deployment.

## Decisions

1. **Workspace as the tenancy unit.** `workspaces` + `workspace_members`
   (composite PK, per-workspace role). Global `user_roles` remains for
   platform-level roles; platform ADMIN passes all workspace gates.
2. **Expand-then-contract tenancy** (ADR-0005): `workspace_id` is a
   nullable, indexed FK on assets, missions, alerts, and incidents.
   Requests carrying `X-Workspace: <slug>` are scoped; requests without
   it see the legacy unscoped view. Contract step (NOT NULL + required
   header) lands once all data is workspace-assigned.
3. **Role enum expansion**, string-backed so it is ALTER-free:
   `soc_manager`, `executive`, `auditor` join admin/operator/analyst/
   viewer. Persona mapping: Platform Admin = global admin; Org Admin =
   workspace-membership admin; the rest map 1:1.
4. **No-enumeration responses.** Unknown workspace slug and
   not-a-member return an identical 404. All invite redemption failure
   modes (unknown, expired, burned, email conflict) return one generic
   422. API key failures return one generic 401.
5. **Invites**: SHA-256 token hash only; burned (used_at set) before the
   account row is created, in the same transaction. Workspace invites
   grant a workspace membership role, not a platform role.
6. **Service accounts** are Users with `is_service_account=True` and an
   unusable password hash (random secret discarded), role capped at
   OPERATOR. **API keys** are `aegis_sk_{prefix}_{secret}` with only the
   prefix and SHA-256 stored; parsing uses maxsplit because urlsafe
   secrets may themselves contain underscores. Authentication via
   `X-API-Key` header sits beside Bearer in the same dependency.
7. **Lockout guards** at both levels: a sole workspace admin cannot
   demote themself and the last admin cannot be removed.
8. **Role-aware frontend routing.** "/" resolves to the caller's home
   workspace by role precedence; nav is filtered per persona; the
   header workspace switcher sets the `X-Workspace` header globally.

## Consequences

- Ingestion alerts remain platform-level (workspace NULL) until sinks
  are taught workspace routing — a deliberate follow-up.
- Migration `c7d9f2b41a55`. 12 new tests; full suite 102 green.
