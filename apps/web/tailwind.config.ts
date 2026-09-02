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
          bg: "var(--as-bg)",
          secondary: "var(--as-bg-secondary)",
          border: "var(--as-border)",
          text: "var(--as-text)",
          muted: "var(--as-text-secondary)",
          primary: "var(--as-primary)",
          positive: "var(--as-positive)",
          negative: "var(--as-negative)",
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
