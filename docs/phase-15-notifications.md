# Phase 15 — Notifications, Preferences, and Brand Rollout

## What shipped

**Notifications (backend)**
- `notifications` table + inbox API: `GET /api/v1/notifications`
  (items + unread count), mark-read, read-all
- Emission wired into: approval requested (fan-out to other workspace
  admins), approval decided (requester notified with reason),
  invite redeemed (inviter notified), critical alert created
  (workspace admins)
- Mute support: emission checks `muted_kinds` in the user's workspace
  preferences — muted events are never written

**Preferences (backend)**
- `workspace_preferences`: one JSON document per (user, workspace) —
  muted kinds, default workspace, dashboard layout
- `GET/PUT /api/v1/preferences` scoped by the `X-Workspace` header

**Frontend**
- Header notification bell: unread badge, dropdown inbox, per-item and
  mark-all read, deep links (approvals -> Org Admin workspace),
  30 s refresh
- Brand rollout: official OrbitalSentinel logo — full lockup on the
  login hero, shield mark in the sidebar and as favicon
  (`public/brand/`)

## Demo beat

Emmanuel requests a sensitive role -> Nelson's bell lights up ->
Nelson approves with a reason -> Emmanuel's bell lights up with
"Your request was approved". Two browsers, one story: separation of
duties you can *see*.

## Follow-ups

- Email/webhook dispatcher reading the notifications table
- Dashboard layout editor consuming the preference document
