# Phase 14 — Custom Roles, Permission Groups, Approval Workflows

## What shipped

**Backend**
- `custom_roles`, `custom_role_permissions`, `approval_requests` tables;
  `workspace_members.custom_role_id` (migration `e1f3a5c72d88`)
- Permission groups catalog: ten building blocks (`fleet-read`,
  `detections-triage`, `response-actions`, `governance`, …) exposed at
  `GET /api/v1/workspaces/rbac/catalog` with the sensitive list
- Role builder API: create (auto-pending when sensitive), list, assign
- Approvals API: list pending, decide — second-admin rule enforced,
  self-approval refused with an explicit message
- `require_permission` now unions workspace grants: a platform viewer
  holding an approved custom "governance" role reads audit logs *only*
  with that workspace active — tenancy and RBAC compose

**Frontend (Org Admin workspace)**
- Role builder: name + permission-group chips (sensitive groups marked
  ●), status column (active / pending / rejected)
- Pending approvals panel with approve/reject, labelled with the exact
  sensitive permissions requested

## Demo script (two admins)

1. As Emmanuel: create role "Compliance Reviewer" with `governance` →
   status **pending**, approval appears
2. Try to approve it yourself → refused: "Approval requires a second
   admin"
3. As Nelson: approve → role **active**
4. Assign it to a viewer → they can open Audit & Compliance, but only
   inside the workspace that granted it

## Follow-ups

- Extend approvals to key minting and sensitive role *assignment*
  (table and endpoints already generic)
- Custom-role personas: map custom roles to a workspace landing page
