# OrbitalSentinel design language — v0 tokens

Operators live in this interface during incidents. Dark, but not the
default "black + neon" look: the base is deep-space indigo, and status
colors follow ops-console convention (amber = attention) rather than
generic dashboard palettes.

## Color
| Token      | Hex     | Role |
|------------|---------|------|
| void       | #0B1020 | App background |
| surface    | #121A31 | Panels, cards |
| raised     | #1A2440 | Hover, elevated |
| line       | #243154 | Borders |
| ink        | #E7ECF8 | Primary text |
| ink-muted  | #8B97B8 | Secondary text |
| ink-faint  | #5A668A | Labels, captions |
| orbit      | #5B8DEF | Primary action (satellite blue) |
| signal     | #F5A524 | Attention / degraded (console amber) |
| critical   | #F0526A | Alerts, failures |
| assured    | #3ECF8E | Healthy, mission-assured |

Rule: status colors mean status, always. `assured/signal/critical` never
decorate; if it's green, the mission is healthy.

## Type
- **Space Grotesk** — display: module titles, key metrics. Technical
  character without novelty.
- **Inter** — body and UI.
- **IBM Plex Mono** — telemetry, IDs, timestamps, coordinates. Anything an
  operator might read aloud over comms renders in mono (`.telemetry`).

## Signature element (Phase 2 target)
The **mission ribbon**: a persistent thin strip under the top bar showing the
live Mission Assurance Score as a horizontal track with per-mission tick
marks. It is the one always-visible element and the product thesis in a
single component: you are never more than a glance from mission health.
