/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        nhm: {
          blue: "#0d47a1",
          teal: "#00695c",
          red: "#c62828",
          orange: "#ef6c00",
          green: "#2e7d32",
        }
      }
    },
  },
  plugins: [],
}

