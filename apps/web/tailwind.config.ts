import type { Config } from "tailwindcss";

/**
 * OrbitalSentinel design tokens v2 — semantic names resolved through
 * CSS variables so dark (default) and light themes swap at the root.
 * Components never reference raw hex. AA-checked pairs per theme live
 * in globals.css.
 */
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: v("navy"),          // app background
        midnight: v("midnight"),  // panels, cards
        raised: v("raised"),      // elevated / hover surfaces
        line: v("line"),          // borders, dividers
        ink: {
          DEFAULT: v("ink"),
          muted: v("ink-muted"),
          faint: v("ink-faint"),
        },
        "on-accent": v("on-accent"), // text on orbital/critical fills
        orbital: { DEFAULT: v("orbital"), deep: v("orbital-deep") },
        quantum: v("quantum"),
        mission: v("mission"),
        amber: v("amber"),
        critical: v("critical"),
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
