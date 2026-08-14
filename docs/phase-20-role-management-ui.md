# Phase 20 — User Role Management UI

Closes the gap surfaced by an actual bug report: role badges looked
interactive but weren't, and underneath, two management paths had no
UI at all.

## What shipped

**Backend**
- `PUT /api/v1/users/{id}/roles` — replace a user's platform roles,
  admin-only, audited (`user.roles_changed`), guarded against removing
  the last platform admin (self or otherwise)
- `DELETE /api/v1/workspaces/{slug}/members/{id}/custom-role` —
  symmetric to the existing assign endpoint
- `MemberRead.custom_role_id` exposed for the UI

**Frontend**
- **Administration** (platform): role badges are now an editable
  multi-select popover per user; a new Clearance column with a live
  dropdown (unclassified / cui / secret, color-coded)
- **Organization Administration**: the Members table's role column is
  now a live `<select>` (was static text); a new Custom role column
  lets an org admin assign or revert any active custom role per member
- Invite role dropdown fixed to include Incident Responder

## Verify

```
cd apps/api && python -m pytest tests/test_role_management.py -q  # 7 tests
```

In the UI: Administration -> click any role badge -> check/uncheck
roles -> Save. Try removing your own admin role as the sole admin —
the exact lockout message appears inline.

## Now fully wired

Platform roles, workspace roles, custom-role assignment, and clearance
are all editable from the UI they were designed to live in, with the
guard rails (lockout, approval-gated sensitive roles, ABAC dominance)
enforced server-side either way.
