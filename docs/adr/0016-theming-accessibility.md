# ADR-0016: Themable Design Tokens and Accessibility Baseline

Status: Accepted — 2026-07-28

## Decisions

1. **Tokens resolve through CSS variables** (`rgb(var(--c-x) / alpha)`)
   with dark as `:root` default and light as a `[data-theme="light"]`
   override. Components keep semantic classes only; the entire theme is
   two variable blocks in `globals.css`.
2. **Light palette is AA-derived, not inverted.** Status colors darken
   for text-on-white (mission #047857, amber #B45309, critical #B91C1C,
   orbital #1D4ED8); dark palette is untouched — it is the brand home.
3. **`on-accent` token** for text on solid accent fills; every solid
   orbital/critical fill carries `text-on-accent`, fixing an implicit
   dark-theme-only assumption (body ink happened to be near-white).
4. **Brand surfaces opt out of theming** via `.brand-panel`, which
   re-scopes the dark variable set locally — the logo's navy field is
   part of the mark, and child token classes resolve correctly inside.
5. **A11y baseline in the stylesheet**: skip-to-content link, `main`
   landmark, `prefers-reduced-motion` reduction, visible focus ring on
   themed offset; placeholder-only inputs received aria-labels.
6. **Theme preference in localStorage** (`aegis.theme`), applied before
   first paint from `main.tsx` to avoid a flash.

## Consequences

- New surfaces are theme-correct by construction if they use tokens.
- A contrast regression test is possible later by evaluating the two
  variable blocks against usage pairs.
