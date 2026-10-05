import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        "card-foreground": "hsl(var(--card-foreground))",
        border: "hsl(var(--border))",
        primary: {
          DEFAULT: "#00f2fe",
          dark: "#00a8cc",
        },
        cyber: {
          cyan: "#00ffff",
          red: "#ff2a5f",
          green: "#00ff9d",
          amber: "#ffb703",
          dark: "#080c14",
          surface: "#0e1526",
          card: "rgba(15, 23, 42, 0.75)",
          border: "rgba(0, 255, 255, 0.2)",
        }
      },
      animation: {
        'pulse-glow': 'pulseGlow 2.5s infinite ease-in-out',
        'scanline': 'scanline 4s linear infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 15px rgba(0, 255, 255, 0.3), 0 0 30px rgba(0, 255, 255, 0.1)' },
          '50%': { boxShadow: '0 0 25px rgba(0, 255, 255, 0.6), 0 0 50px rgba(0, 255, 255, 0.25)' },
        },
        scanline: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(1000%)' },
        }
      }
    },
  },
  plugins: [],
};
export default config;
