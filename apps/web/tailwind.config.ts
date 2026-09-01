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
        aq: {
          bg: "var(--aq-bg)",
          secondary: "var(--aq-bg-secondary)",
          border: "var(--aq-border)",
          text: "var(--aq-text)",
          muted: "var(--aq-text-secondary)",
          primary: "var(--aq-primary)",
          positive: "var(--aq-positive)",
          negative: "var(--aq-negative)",
        },
      },
      borderRadius: {
        aq: "var(--aq-radius)",
      },
      boxShadow: {
        aq: "var(--aq-shadow)",
        "aq-lg": "var(--aq-shadow-lg)",
      },
      transitionDuration: {
        aq: "200ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
