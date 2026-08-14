# ADR-0020: User Role Management UI

Status: Accepted — 2026-07-28

## Context

Phase 12/14/17 built the full role model (platform roles, workspace
roles, custom roles, clearance) and most of the backend, but the UI
only ever *displayed* roles as read-only badges. Two backend gaps also
existed: no endpoint to change a user's platform roles after creation,
and no endpoint to revert a member off a custom role.

## Decisions

1. **Platform role changes get a new `UserService.set_roles`**,
   wholesale-replacing role_assignments, guarded identically to the
   existing workspace-admin lockout (ADR-0012): the sole platform admin
   cannot self-demote, and no actor can strip the last admin's admin
   role. Message distinguishes self vs. other for clarity.
2. **Custom-role unassignment is symmetric to assignment** — clears
   `membership.custom_role_id`, auditing only when a role was actually
   removed (no-op unassign of an already-bare membership isn't logged
   as a change).
3. **UI wiring, not new capability, for workspace roles** — the
   `setMemberRole`/`assignCustomRole` endpoints already existed
   (Phase 12/14) but nothing in the UI called them. The Members table
   now has live `<select>` controls.
4. **Role badges become the entry point, not the editor.** Account page
   badges (fixed prior turn) navigate to a role's workspace; role
   *changes* happen in Administration (platform) or Organization
   Administration (workspace) — consistent with who is authorized to
   make each kind of change.
5. **Errors surface inline**, not as toasts — a blocked lockout attempt
   shows the exact server message next to the control that triggered
   it.

## Consequences

- `MemberRead.custom_role_id` added so the UI can reflect current
  custom-role assignment without a second round trip.
- Fixed incidentally: the invite role dropdown was missing
  `incident_responder` since Phase 13 added that role after the
  dropdown was written.
- 7 new tests; suite 145 green; zero migrations (uses existing columns).
