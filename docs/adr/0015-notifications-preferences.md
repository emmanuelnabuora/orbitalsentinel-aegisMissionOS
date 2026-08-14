# ADR-0015: In-App Notifications and Workspace Preferences

Status: Accepted — 2026-07-28

## Decisions

1. **Synchronous, in-transaction emission.** Notification rows are added
   in the same session as the triggering mutation (approval, invite
   redemption, critical alert) and commit with it — no queue, no
   delivery race, consistent with the modular monolith (ADR-0001).
   Fan-out is bounded (workspace admins), so latency is negligible.
2. **Emission points, not polling rules.** Producers name a `kind`
   (`approval.requested`, `approval.approved|rejected`,
   `member.joined`, `alert.critical`); the requester of a change is
   excluded from admin fan-out (no self-notification).
3. **Mutes honored at emission time** via
   `workspace_preferences.data.muted_kinds` — muted events are never
   stored, so unread counts stay honest and no read-side filtering.
4. **One JSON preference document per (user, workspace)** covering
   muted kinds, default-workspace flag, and dashboard layout. Schema
   lives in the document, versioned by convention — preferences are
   UI-owned data, not domain state.
5. **Inbox API is user-scoped only**; workspace_id on a notification is
   provenance, not access control. Reading another user's notification
   404s.

## Consequences

- Email/webhook delivery later = a dispatcher reading the same table.
- Migration `f4a6b8d93e11`; 5 new tests; suite 118 green.
