/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ChatHub-inspired dark palette
        bg: {
          primary: '#0f0f13',
          secondary: '#1a1a24',
          tertiary: '#22222e',
          card: '#1e1e2a',
          hover: '#2a2a38',
          border: '#2e2e3d',
        },
        accent: {
          blue: '#4f8ef7',
          'blue-hover': '#6aa0f8',
          purple: '#8b5cf6',
          green: '#10b981',
          orange: '#f59e0b',
          red: '#ef4444',
        },
        text: {
          primary: '#e8e8f0',
          secondary: '#9999b3',
          muted: '#6666888',
          disabled: '#444458',
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-in-out',
        'slide-in': 'slideIn 0.2s ease-out',
        cursor: 'cursor 1s step-end infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-8px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        cursor: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
    },
  },
  plugins: [],
}
