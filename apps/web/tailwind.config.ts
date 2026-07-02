import type { Config } from "tailwindcss";

// Design tokens are centralized here (CLAUDE.md §4/§18).
// Version 2, light-first enterprise palette: warm-white/cream surfaces, hairline
// dark-brown-alpha borders, a dark-brown primary accent, a restrained gold highlight
// (decorative only — see DESIGN_SYSTEM.md), and muted semantic colors.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./features/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg)",
        canvas: "var(--canvas)",
        surface: {
          DEFAULT: "var(--surface)",
          elevated: "var(--surface-2)",
          hover: "var(--surface-hover)",
        },
        hairline: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        foreground: {
          DEFAULT: "var(--text)",
          secondary: "var(--text-2)",
          muted: "var(--text-3)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          soft: "var(--accent-soft)",
          foreground: "var(--accent-fg)",
        },
        gold: {
          DEFAULT: "var(--gold)",
          soft: "var(--gold-soft)",
        },
        success: {
          DEFAULT: "var(--success)",
          soft: "var(--success-soft)",
        },
        warning: {
          DEFAULT: "var(--warning)",
          soft: "var(--warning-soft)",
        },
        danger: {
          DEFAULT: "var(--danger)",
          soft: "var(--danger-soft)",
        },
      },
      borderColor: {
        DEFAULT: "var(--border)",
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "-apple-system",
          "BlinkMacSystemFont",
          "SF Pro Text",
          "Segoe UI",
          "Roboto",
          "system-ui",
          "sans-serif",
        ],
        // Arabic locale stack, wired up when next-intl lands in V2-P2.
        "sans-arabic": ["Tajawal", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SF Mono", "SFMono-Regular", "JetBrains Mono", "Menlo", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.02em" }],
      },
      borderRadius: {
        "4xl": "1.75rem",
      },
      boxShadow: {
        soft: "0 1px 2px 0 rgba(43,32,21,0.06), 0 1px 1px 0 rgba(43,32,21,0.04)",
        elevated: "0 1px 0 0 rgba(255,255,255,0.6) inset, 0 8px 24px -8px rgba(43,32,21,0.16)",
        glow: "0 0 0 1px var(--accent-soft), 0 8px 40px -12px rgba(91,58,34,0.25)",
      },
      backgroundImage: {
        "accent-fade":
          "linear-gradient(180deg, rgba(91,58,34,0.08) 0%, rgba(91,58,34,0) 70%)",
        "surface-grain":
          "radial-gradient(120% 120% at 50% 0%, rgba(255,255,255,0.6) 0%, rgba(255,255,255,0) 45%)",
        "hairline-x":
          "linear-gradient(90deg, rgba(59,44,31,0) 0%, rgba(59,44,31,0.12) 50%, rgba(59,44,31,0) 100%)",
      },
      transitionTimingFunction: {
        "out-soft": "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
