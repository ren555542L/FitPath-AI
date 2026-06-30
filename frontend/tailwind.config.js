/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Safe/calm lifestyle design system color tokens
        brand: {
          50: '#f0faf6',
          100: '#d7f3e8',
          200: '#b2e6d2',
          300: '#7ed2b4',
          400: '#4ab994',
          500: '#2c9d78',  // Primary Forest Green accent
          600: '#207e5f',
          700: '#1a654e',
          800: '#16513f',
          900: '#134335',
        },
      }
    },
  },
  plugins: [],
}
