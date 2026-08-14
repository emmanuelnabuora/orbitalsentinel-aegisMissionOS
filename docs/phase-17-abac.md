# Phase 17 — ABAC: Clearance and Classification

Closes the final item of the Phase 13 RBAC spec reconciliation.

## What shipped

- Classification markings (`unclassified` / `cui` / `secret`) on
  assets, missions, alerts, incidents; clearance on users; dominance
  enforced everywhere reads happen:
  - **Lists**: SQL-level filter — unseen rows are never serialized
  - **Detail**: 404 identical to true absence — existence never leaks
- **Admins are not exempt.** Creating a SECRET asset does not let you
  read it; need-to-know is universal (tested).
- `PUT /api/v1/users/{id}/clearance` (admin, audited); classification
  settable at asset/alert creation and returned in reads
- UI: CUI/SECRET chips beside asset and alert names in the Operator
  and Analyst workspaces; unclassified renders clean

## Demo beat

Create "SECRET-SAT" as a marked asset -> it vanishes from your own
fleet view -> grant yourself SECRET clearance (audited) -> it appears
with a red SECRET chip. Need-to-know, live, in ninety seconds.

## Spec status: COMPLETE

Every section of the RBAC/workspace specification is now implemented
or explicitly documented: 8 roles + custom roles, fine-grained
permissions, permission groups, approval workflows, ABAC, tenant
isolation, audit, notifications, preferences, dark + light themes,
WCAG baseline, permission-denied and session-expired screens.

## Follow-ups

- Marking changes post-creation via the approval workflow
- Compartments/caveats if a customer's scheme requires them
