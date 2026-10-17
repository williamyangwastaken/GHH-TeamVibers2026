import type { Config } from "tailwindcss";

// Design tokens come from the CSS variables in app/globals.css (ported verbatim
// from public/demo/prototype/clearbill.html), so utilities and the prototype's
// component classes always share one palette.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  corePlugins: {
    // The prototype's CSS was designed on browser defaults (list bullets, <p>
    // margins, bold <h4>). Preflight would silently restyle those, so it is off.
    // Side effect: `border-*` utilities don't reset the other sides, so write
    // borders as `1px solid var(--line)` styles instead.
    preflight: false,
  },
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: { DEFAULT: "var(--surface)", 2: "var(--surface-2)" },
        sage: { DEFAULT: "var(--sage)", 2: "var(--sage-2)" },
        ink: { DEFAULT: "var(--ink)", 2: "var(--ink-2)", 3: "var(--ink-3)" },
        line: { DEFAULT: "var(--line)", 2: "var(--line-2)" },
        primary: {
          DEFAULT: "var(--primary)",
          2: "var(--primary-2)",
          ink: "var(--primary-ink)",
          soft: "var(--primary-soft)",
        },
        amber: { DEFAULT: "var(--amber)", bg: "var(--amber-bg)", line: "var(--amber-line)" },
        clay: { DEFAULT: "var(--clay)", bg: "var(--clay-bg)" },
        teal: { DEFAULT: "var(--teal-ink)", bg: "var(--teal-bg)" },
        focus: "var(--focus)",
      },
      fontFamily: {
        sans: ["var(--font-figtree)", "Figtree", "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ["var(--font-instrument-serif)", "Instrument Serif", "Georgia", "serif"],
        hand: ["var(--font-caveat)", "Caveat", "cursive"],
      },
      borderRadius: {
        card: "var(--r)",
        "card-sm": "var(--r-sm)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        card: "var(--shadow)",
        lg: "var(--shadow-lg)",
      },
    },
  },
  plugins: [],
};

export default config;
