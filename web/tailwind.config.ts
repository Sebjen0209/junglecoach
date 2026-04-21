import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          red: "#E24B4A",
          amber: "#EF9F27",
          grey: "#444441",
          bg: "#0A0A0F",
          surface: "#13131A",
          border: "#1E1E2A",
        },
        arcane: {
          gold: "#f0c040",
          magenta: "#c850ff",
          cyan: "#00e5ff",
          crimson: "#ff3366",
          indigo: "#0d0d2b",
          teal: "#051a2e",
          deep: "#080818",
        },
      },
      fontFamily: {
        sans: ["var(--font-barlow)", "system-ui", "sans-serif"],
        display: ["var(--font-cinzel)", "serif"],
        sub: ["var(--font-rajdhani)", "system-ui", "sans-serif"],
        barlow: ["var(--font-barlow)", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "aurora": "linear-gradient(135deg, #0d0d2b 0%, #051a2e 35%, #0d1a3a 60%, #1a0d2e 100%)",
      },
      keyframes: {
        "hue-drift": {
          "0%, 100%": { filter: "hue-rotate(0deg)" },
          "50%": { filter: "hue-rotate(30deg)" },
        },
        "aurora-shift": {
          "0%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
          "100%": { backgroundPosition: "0% 50%" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% center" },
          "100%": { backgroundPosition: "200% center" },
        },
        "ken-burns": {
          "0%": { transform: "scale(1) translate(0, 0)" },
          "50%": { transform: "scale(1.06) translate(-1%, -1%)" },
          "100%": { transform: "scale(1) translate(0, 0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-12px)" },
        },
        "radial-pulse": {
          "0%, 100%": { opacity: "0.4", transform: "scale(1)" },
          "50%": { opacity: "0.8", transform: "scale(1.15)" },
        },
      },
      animation: {
        "hue-drift": "hue-drift 8s ease-in-out infinite",
        "aurora-shift": "aurora-shift 12s ease infinite",
        shimmer: "shimmer 3s linear infinite",
        "ken-burns": "ken-burns 20s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
        "radial-pulse": "radial-pulse 4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
