# ADR-0014: Custom Roles, Permission Groups, and Approval Workflows

Status: Accepted — 2026-07-28

## Decisions

1. **Custom roles are workspace-scoped DB rows** (`custom_roles` +
   `custom_role_permissions`), composed from **code-defined permission
   groups** (`PERMISSION_GROUPS`). Groups stay in code because they are
   product vocabulary — reviewed like code, versioned with the
   permission catalog — while the roles built from them are tenant data.
2. **Assignment replaces, not augments.** A membership with
   `custom_role_id` uses the custom role's permission set in place of
   its built-in role's for workspace-scoped authorization. One source
   of truth per membership; no additive ambiguity.
3. **Effective permissions** = platform-role permissions ∪ workspace
   grant (built-in or custom) when `X-Workspace` is active. Enforced
   inside `require_permission`; endpoints unchanged.
4. **Approval workflow (separation of duties).** A custom role
   containing any `SENSITIVE_PERMISSIONS` (`incidents:respond`,
   `audit:read`, `users:manage`, `workspace:manage`, `keys:manage`) is
   created `pending` with an `ApprovalRequest`. Only a *different*
   workspace admin can decide; self-approval returns 422. Pending and
   rejected roles are unassignable and answer identically to unknown
   roles (no state enumeration).
5. **Retired permissions degrade safely**: unknown stored permission
   strings are ignored at resolution time, so shrinking the catalog
   never grants or crashes.

## Consequences

- The Phase 13 promise held: custom roles landed as data + one
  dependency change, zero endpoint rewrites.
- Approval requests are generic (`kind` + `subject_id` + payload), so
  future sensitive actions (key minting, role assignment) reuse the
  same table and endpoints.
- Migration `e1f3a5c72d88`; 6 new tests; suite 113 green.
