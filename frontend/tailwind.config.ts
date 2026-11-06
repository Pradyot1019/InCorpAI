import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

// Design tokens. Colours are exposed as CSS variables (see src/index.css) so a Lovable
// rebuild or a theme switch only has to change the variables.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "rgb(var(--paper) / <alpha-value>)",
        sheet: "rgb(var(--sheet) / <alpha-value>)",
        ink: {
          DEFAULT: "rgb(var(--ink) / <alpha-value>)",
          soft: "rgb(var(--ink-soft) / <alpha-value>)",
          faint: "rgb(var(--ink-faint) / <alpha-value>)",
        },
        rule: "rgb(var(--rule) / <alpha-value>)",
        registry: {
          DEFAULT: "rgb(var(--registry) / <alpha-value>)",
          deep: "rgb(var(--registry-deep) / <alpha-value>)",
          wash: "rgb(var(--registry-wash) / <alpha-value>)",
        },
        stamp: {
          DEFAULT: "rgb(var(--stamp) / <alpha-value>)",
          wash: "rgb(var(--stamp-wash) / <alpha-value>)",
        },
        notice: {
          DEFAULT: "rgb(var(--notice) / <alpha-value>)",
          wash: "rgb(var(--notice-wash) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ['"Public Sans Variable"', "system-ui", "sans-serif"],
        serif: ['"Source Serif 4 Variable"', "Georgia", "serif"],
      },
      fontSize: {
        // modular scale ~1.2 (minor third) anchored at 15px UI text
        xs: ["0.75rem", { lineHeight: "1.1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.9375rem", { lineHeight: "1.5rem" }],
        lg: ["1.125rem", { lineHeight: "1.65rem" }],
        xl: ["1.35rem", { lineHeight: "1.8rem" }],
        "2xl": ["1.62rem", { lineHeight: "2.05rem" }],
        "3xl": ["2.33rem", { lineHeight: "2.6rem" }],
      },
      borderRadius: { field: "6px", panel: "10px" },
      keyframes: {
        stamp: {
          "0%": { transform: "scale(1.9) rotate(-14deg)", opacity: "0" },
          "60%": { transform: "scale(0.94) rotate(-9deg)", opacity: "1" },
          "100%": { transform: "scale(1) rotate(-9deg)", opacity: "1" },
        },
        caret: { "0%,100%": { opacity: "1" }, "50%": { opacity: "0" } },
      },
      animation: {
        stamp: "stamp 320ms cubic-bezier(.2,.9,.3,1.2) both",
        caret: "caret 1s steps(1) infinite",
      },
    },
  },
  plugins: [typography],
} satisfies Config;
