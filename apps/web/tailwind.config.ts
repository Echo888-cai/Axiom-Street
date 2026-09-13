import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        as: {
          bg: "rgb(var(--as-bg-rgb) / <alpha-value>)",
          secondary: "rgb(var(--as-secondary-rgb) / <alpha-value>)",
          border: "rgb(var(--as-border-rgb) / <alpha-value>)",
          text: "rgb(var(--as-text-rgb) / <alpha-value>)",
          muted: "rgb(var(--as-muted-rgb) / <alpha-value>)",
          primary: "rgb(var(--as-primary-rgb) / <alpha-value>)",
          positive: "rgb(var(--as-positive-rgb) / <alpha-value>)",
          negative: "rgb(var(--as-negative-rgb) / <alpha-value>)",
          warning: "rgb(var(--as-warning-rgb) / <alpha-value>)",
        },
      },
      borderRadius: {
        as: "var(--as-radius)",
      },
      boxShadow: {
        as: "var(--as-shadow)",
        "as-lg": "var(--as-shadow-lg)",
      },
      transitionDuration: {
        as: "200ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
