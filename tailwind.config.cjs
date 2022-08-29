/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // add new font family
        main: ["Inter", "sans-serif"],
      },
    },
    colors: {
      // custom color palette
      primary: "#441151",
      darkgold: "#CCA43B",
      secondary: "#EE85B5",
      violet: "#883677",
      congo: "##FF958C",
      success: "#5FC790",
      warning: "#FFA600",
      danger: "#FF5630",
      dark: "#2E3A44",
      info: "#1CA7EC",
      black: "#2E3A44",
      grey1: "#A0AABF",
      grey2: "#C0C6D4",
      grey3: "#E3E8F1",
      light: "#F9FBFC",
      white: "#FFF",
    },
  },
  plugins: [],
};
