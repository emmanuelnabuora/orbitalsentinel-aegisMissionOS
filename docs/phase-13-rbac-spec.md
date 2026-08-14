# Phase 13 — RBAC Specification Reconciliation

This document maps the full RBAC/workspace specification onto AEGIS
MissionOS: what is live, what shipped in this phase, and what is
scheduled. It is the authoritative permission matrix.

## Spec-to-implementation map

| Spec area | Status | Where |
|---|---|---|
| JWT + refresh + session mgmt | Live (Phase 2-3) | `core/security.py`, refresh rotation ADR-0003 |
| MFA | Live (Phase 6-identity) | TOTP + recovery codes, ADR-0007 |
| SSO / IdP config | Live | OIDC, group->role re-sync on login |
| Multi-tenancy / tenant isolation | Live (Phase 12) | Workspaces, X-Workspace scoping, ADR-0012 |
| 8 roles | Live (13) | `incident_responder` added this phase |
| Fine-grained permissions | **Phase 13** | `core/permissions.py`, `require_permission` |
| Custom roles | Foundation laid | Role->permission map is data-shaped; DB-backed custom roles are a follow-up migration, not a redesign |
| ABAC | Scheduled | Attribute checks slot into `require_permission` once needed (classification level, mission ownership) |
| Role-aware navigation & landing | Live (Phase 12-13) | 8 persona workspaces, RoleHome routing |
| Permission-denied screen | **Phase 13** | `/forbidden` |
| Session-expired handling | Live | `setSessionExpiredHandler` -> login |
| Audit logging | Live | Every access-lifecycle mutation audited; auditor read endpoint |
| API keys / service accounts | Live (Phase 12) | `aegis_sk_*`, X-API-Key |
| Invites / user mgmt | Live (Phase 11-12) | Burn-on-use tokens, lockout guards |
| Dark theme | Live | AEGIS design system |
| Light theme | Scheduled | Token-level work; tracked below |
| Dashboard prefs / notifications tables | Scheduled | Phase 14 candidates |
| Approval workflows | Scheduled | Pairs with custom roles |

## Permission matrix

Permissions are the authorization unit; roles are bundles. Platform
ADMIN implicitly holds all. See `core/permissions.py` for the source of
truth; summary:

| Role | Read | Write/Act | Restricted from |
|---|---|---|---|
| Platform Admin | everything | everything | — |
| Org Admin (workspace) | org scope | members, invites, keys | other tenants |
| Mission Operator | fleet, alerts | assets, missions, twin, triage | audit, user mgmt |
| Security Analyst | detections, intel | triage, intel mgmt | asset/mission writes, audit |
| SOC Manager | detections, reports | triage, incident mgmt, report gen | asset writes, audit |
| Incident Responder | detections | triage, incident mgmt, **response actions** | asset writes, audit, intel mgmt |
| Executive | missions, reports, incidents | — | all writes, audit |
| Auditor | audit, reports | — | all operational modules |

`incidents:respond` (containment/response actions) is held only by
Incident Responder and Admin — deliberate separation of duties from
SOC Manager, who manages but does not execute response.

## Adoption path

`require_permission(Permission.X)` is the gate for all new endpoints
(audit router converted as the exemplar). Existing `require_roles`
gates keep working; they migrate opportunistically as endpoints are
touched. When custom roles land, only `ROLE_PERMISSIONS` moves to a
table — no endpoint changes.

## Scheduled next (proposed Phase 14)

1. Light theme (design tokens already centralized in Tailwind config)
2. `dashboard_layouts` + `notification_preferences` tables + API
3. DB-backed custom roles + approval workflows
4. ABAC attributes: mission ownership, classification markings
