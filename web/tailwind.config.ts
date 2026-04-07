import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        forest: "#0b3d2e",
        mist: "#f5f8f7",
        accent: "#1f7a4d",
      },
      fontFamily: {
        heading: ["\"Space Grotesk\"", "\"Segoe UI\"", "sans-serif"],
        body: ["\"Source Sans 3\"", "\"Segoe UI\"", "sans-serif"],
      },
      boxShadow: {
        soft: "0 10px 30px rgba(15, 23, 42, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
