import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Base colors from recipe_monitor.html CSS variables
        bg: {
          DEFAULT: '#0b1020',
          dark: '#0a0f1f',
        },
        panel: {
          DEFAULT: '#121a33',
          alt: '#0f1630',
          darker: '#0c1226',
        },
        text: {
          DEFAULT: '#e5e7eb',
          muted: '#9aa4bf',
          bright: '#eaf1ff',
          light: '#c9d3f9',
          lightest: '#c6d0f5',
          slate: '#cbd5e1',
        },
        primary: {
          DEFAULT: '#3b82f6',
          dark: '#2f66c4',
        },
        success: {
          DEFAULT: '#10b981',
          dark: '#1d3f34',
        },
        danger: {
          DEFAULT: '#ef4444',
          dark: '#c43333',
          darker: '#5a2222',
        },
        warning: {
          DEFAULT: '#f59e0b',
          dark: '#c07d0a',
        },
        accent: '#6473c1',
        border: {
          DEFAULT: '#1e2a55',
          dark: '#263366',
          darker: '#233064',
          dotted: '#1c2752',
        },
        // Status colors
        status: {
          idle: '#93a1c9',
          running: '#3b82f6',
          paused: '#f59e0b',
          completed: '#10b981',
          failed: '#ef4444',
        },
        // Component-specific colors
        input: {
          bg: '#0e1530',
          border: '#263366',
        },
      },
      backgroundImage: {
        'gradient-main': 'linear-gradient(180deg, #0a0f1f 0%, #0b1020 100%)',
        'gradient-panel': 'linear-gradient(180deg, #121a33 0%, #0f1630 100%)',
      },
      boxShadow: {
        'panel': '0 10px 30px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.03)',
        'toast': '0 8px 24px rgba(0,0,0,0.35)',
      },
      animation: {
        'pulse-status': 'pulse 2s infinite',
      },
      keyframes: {
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
      },
    },
  },
  plugins: [],
};

export default config;
