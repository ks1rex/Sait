/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: { DEFAULT: '#14a89a', dark: '#0e8a7d' },
        navy: { DEFAULT: '#1a2332', light: '#243044', lighter: '#2d3d55' },
      },
    },
  },
  plugins: [],
}

