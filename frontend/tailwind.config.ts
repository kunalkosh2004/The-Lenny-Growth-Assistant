import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#171717",
        paper: "#fbfaf7",
        line: "#ddd8cf",
        accent: "#0f766e",
        warn: "#b45309",
      },
    },
  },
  plugins: [],
};

export default config;
