# ADR-0003: Refresh-token rotation with family revocation; role-based access

Status: accepted · Date: 2026-07-09

## Refresh tokens
Opaque 256-bit secrets, stored only as SHA-256 hashes. Each login opens a
token *family*; every refresh revokes the presented token and issues a
successor in the same family. Presenting an already-revoked token is treated
as evidence of theft (an attacker or the client replayed a rotated token):
the entire family is revoked and `auth.refresh_reuse_detected` is audited.
Login failures return a single generic message — no account-existence oracle.

## RBAC
Four roles: admin, operator, analyst, viewer. Enforcement is a FastAPI
dependency (`require_roles`) at the router layer; admin passes every check.
Mutations require operator; deletes and user management require admin.
Roles ride in the JWT for cheap checks, but `get_current_user` re-loads the
user each request, so deactivation takes effect within one access-token TTL
(≤15 min) even for stolen tokens.

## Audit
`AuditService.record()` is called by domain services inside the same
transaction as the change, so the audit row commits atomically with the
mutation. Rows carry actor, action, resource, request_id (correlates with
HTTP logs), and a structured detail payload. The table is append-only by
convention now; a DB-level revoke of UPDATE/DELETE lands with deployment.
