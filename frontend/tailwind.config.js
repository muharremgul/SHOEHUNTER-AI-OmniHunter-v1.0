/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Outfit", "sans-serif"],
        sans: ["IBM Plex Sans", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      colors: {
        background: "#09090B",
        surface: "#18181B",
        surfaceHover: "#27272A",
        primary: "#CCFF00",
        accent: "#FF3B30",
        borderc: "#27272A",
        mutedfg: "#A1A1AA",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        scanline: {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
      },
      animation: {
        fadeUp: "fadeUp 0.4s ease-out both",
        scanline: "scanline 1.2s linear infinite",
      },
    },
  },
  plugins: [],
};
