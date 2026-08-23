/** @type {import('tailwindcss').Config} */
import typography from '@tailwindcss/typography'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // 主色：医药行业 teal/cyan 色系
        brand: {
          50: '#f0fdfa',
          100: '#ccfbf1',
          200: '#99f6e4',
          300: '#5eead4',
          400: '#2dd4bf',
          500: '#14b8a6',
          600: '#0d9488', // primary
          700: '#0f766e',
          800: '#115e59',
          900: '#134e4a',
        },
        // F-重构：语义化 surface 色阶（单一事实来源，自带 dark 值）
        // 与 index.css 暗色覆盖保持同一套暖灰棕；class 中可直接用 dark:bg-surface-*
        surface: {
          app: '#f8fafc', // slate-50
          'app-dark': '#171310',
          card: '#ffffff', // white
          'card-dark': '#242019',
          header: '#ffffff', // white
          'header-dark': '#1e1a15',
          sidebar: '#ffffff', // white
          'sidebar-dark': '#1e1a15',
          raised: '#f1f5f9', // slate-100
          'raised-dark': '#2a2520',
          hover: 'rgba(148,163,184,0.08)',
          'hover-dark': 'rgba(42,37,32,0.5)',
          'border-subtle': 'rgb(226 232 240)',
          'border-subtle-dark': 'rgba(120,100,75,0.15)',
        },
        // 医药专用语义色
        medical: {
          success: '#10b981', // emerald-500
          warning: '#f59e0b', // amber-500
          danger: '#f43f5e', // rose-500
          info: '#0ea5e9', // sky-500
        },
      },
      fontFamily: {
        sans: ['"PingFang SC"', '"Noto Sans SC"', '"Inter"', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SF Mono', 'Menlo', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.06)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)',
        dropdown: '0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.06)',
      },
      borderRadius: {
        xl: '0.75rem',
        '2xl': '1rem',
      },
      // F16：语义化 surface / border 颜色 token
      // 注意：Tailwind 已有 border 色，这里用 borderColor 扩展避免覆盖
      borderColor: {
        subtle: 'rgb(241 245 249)', // slate-100
        DEFAULT: 'rgb(226 232 240)', // slate-200
        strong: 'rgb(203 213 225)', // slate-300
      },
      spacing: {
        sidebar: '16rem', // 256px
        'chat-input': '4.5rem',
      },
      animation: {
        shimmer: 'shimmer 2s linear infinite',
        'fade-in': 'fade-in 0.2s ease-out',
        'slide-in': 'slide-in 0.3s ease-out',
        'ai-pulse': 'ai-pulse 2s ease-in-out infinite',
        'ai-alert': 'ai-alert-pulse 2s ease-in-out infinite',
        'ai-progress': 'ai-progress 1.5s ease-in-out infinite',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-in': {
          '0%': { transform: 'translateY(8px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'ai-pulse': {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 0 0 rgba(20, 184, 166, 0.4)' },
          '50%': { opacity: '0.85', boxShadow: '0 0 0 6px rgba(20, 184, 166, 0)' },
        },
        'ai-alert-pulse': {
          '0%, 100%': { borderColor: 'rgb(245 158 11 / 0.3)' },
          '50%': { borderColor: 'rgb(245 158 11 / 0.8)' },
        },
        'ai-progress': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(200%)' },
        },
      },
    },
  },
  plugins: [typography],
}
