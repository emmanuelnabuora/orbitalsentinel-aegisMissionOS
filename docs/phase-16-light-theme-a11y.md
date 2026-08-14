# Phase 16 — Light Theme and WCAG 2.2 AA Pass

## What shipped

- **Light theme**: full token swap via CSS variables; toggle in the
  header (sun/moon), persisted, applied pre-paint. Dark remains the
  default and the brand home.
- **AA contrast**: light status/action colors derived for text-on-white
  (>= 4.5:1 on their usage surfaces); `on-accent` token added and every
  solid accent fill converted — this also fixed a latent dark-only
  assumption in seven files.
- **Brand integrity**: the login hero keeps the dark palette in both
  themes via `.brand-panel` token re-scoping, so the lockup always sits
  on its navy field.
- **Accessibility**: skip-to-content link, `#main` landmark,
  `prefers-reduced-motion` respected globally, aria-labels on
  placeholder-only inputs, notification bell announces unread count.

## Verify

Toggle the sun/moon in the header: every page, badge, and button should
remain legible; the login page's left panel stays navy by design.

## Remaining from the RBAC spec reconciliation

- Phase 17: ABAC (attribute predicates — classification, mission
  ownership) inside `require_permission`
