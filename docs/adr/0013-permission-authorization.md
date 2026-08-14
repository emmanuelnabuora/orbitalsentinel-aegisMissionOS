# ADR-0013: Permission-Based Authorization

Status: Accepted — 2026-07-28

## Decision

Authorization checks name permissions (`assets:write`,
`incidents:respond`), not roles. Roles are permission bundles defined in
`core/permissions.py` (`ROLE_PERMISSIONS`); platform ADMIN implicitly
holds all permissions. New endpoints use `require_permission`;
`require_roles` remains for legacy gates and migrates opportunistically.

Rationale: least privilege becomes auditable (the matrix is one file),
separation of duties is expressible (only Incident Responder holds
`incidents:respond`), and future custom roles become a data migration
(role->permission table) rather than an endpoint rewrite. ABAC slots in
later as attribute predicates inside the same dependency.

## Consequences

- Eighth role `incident_responder` added (string enum, ALTER-free).
- Tests assert the matrix (admin totality, least-privilege spot checks,
  responder exclusivity of response actions).
