/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#F6F7FB',
        card: '#FFFFFF',
        border: '#ECEEF5',
        'border-soft': '#F2F3F8',
        text: '#1D2439',
        muted: '#7C88A6',
        'muted-2': '#A8B0C4',
        primary: '#FF6B4A',
        'primary-dark': '#F0522F',
        'primary-soft': '#FFEEE8',
        navy: '#1B2540',
        'navy-soft': '#EEF0F7',
        teal: '#0FA3A3',
        'teal-soft': '#E2F6F6',
        gold: '#F4B400',
        'gold-soft': '#FDF2D8',
        pink: '#EF5DA8',
        'pink-soft': '#FDEAF4',
        purple: '#7C5CFC',
        'purple-soft': '#F0ECFE',
        success: '#1FAE59',
        'success-dark': '#178C48',
        'success-soft': '#E7F8EE',
        danger: '#F0464B',
        'danger-soft': '#FDEAEA',
        info: '#3E7BFA',
        'info-soft': '#EAF1FE',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: '14px',
        DEFAULT: '9px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(20,25,60,0.03), 0 6px 20px rgba(20,25,60,0.05)',
        sm: '0 1px 2px rgba(20,25,60,0.04)',
      },
      keyframes: {
        softPulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        slideIn: {
          from: { transform: 'translateX(100%)', opacity: '0' },
          to: { transform: 'translateX(0)', opacity: '1' },
        },
        fadeUp: {
          from: { transform: 'translateY(8px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        pulse: 'softPulse 1.8s ease-in-out infinite',
        slideIn: 'slideIn 0.25s ease-out',
        fadeUp: 'fadeUp 0.2s ease-out',
        shimmer: 'shimmer 1.5s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
