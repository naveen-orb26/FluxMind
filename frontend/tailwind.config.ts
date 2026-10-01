import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "#0b0f19",
        surface: "#111827",
        surfaceLight: "#1f2937",
        border: "#374151",
        primary: {
          DEFAULT: "#0ea5e9", // cyan/sky
          hover: "#0284c7",
          glow: "rgba(14, 165, 233, 0.25)"
        },
        solar: {
          DEFAULT: "#eab308", // amber/yellow
          glow: "rgba(234, 179, 8, 0.25)"
        },
        carbon: {
          clean: "#10b981", // emerald
          dirty: "#ef4444", // red
        },
        battery: {
          DEFAULT: "#8b5cf6", // violet
          glow: "rgba(139, 92, 246, 0.25)"
        }
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
