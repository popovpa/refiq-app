/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(220 16% 90%)',
        input: 'hsl(220 16% 90%)',
        ring: 'hsl(174 72% 40%)',
        background: 'hsl(220 20% 97%)',
        foreground: 'hsl(222 32% 14%)',
        primary: {
          DEFAULT: 'hsl(174 72% 40%)',
          foreground: 'hsl(0 0% 100%)',
        },
        brand: {
          DEFAULT: 'hsl(248 78% 62%)',
          soft: 'hsl(248 90% 96%)',
          foreground: 'hsl(0 0% 100%)',
        },
        secondary: {
          DEFAULT: 'hsl(220 18% 96%)',
          foreground: 'hsl(222 32% 14%)',
        },
        muted: {
          DEFAULT: 'hsl(220 18% 96%)',
          foreground: 'hsl(220 10% 46%)',
        },
        accent: {
          DEFAULT: 'hsl(174 60% 95%)',
          foreground: 'hsl(174 72% 32%)',
        },
        destructive: {
          DEFAULT: 'hsl(0 84% 60%)',
          foreground: 'hsl(0 0% 100%)',
        },
        success: {
          DEFAULT: 'hsl(152 69% 40%)',
          foreground: 'hsl(0 0% 100%)',
        },
        warning: {
          DEFAULT: 'hsl(32 95% 52%)',
          foreground: 'hsl(0 0% 100%)',
        },
        info: {
          DEFAULT: 'hsl(210 90% 56%)',
          foreground: 'hsl(0 0% 100%)',
        },
        pink: {
          soft: 'hsl(330 85% 96%)',
          DEFAULT: 'hsl(330 80% 60%)',
        },
        card: {
          DEFAULT: 'hsl(0 0% 100%)',
          foreground: 'hsl(222 32% 14%)',
        },
      },
      borderRadius: {
        xl: '16px',
        lg: '12px',
        md: '10px',
        sm: '8px',
      },
      boxShadow: {
        card: '0 1px 2px rgba(16, 24, 40, 0.04), 0 4px 16px rgba(16, 24, 40, 0.04)',
        soft: '0 8px 24px rgba(16, 24, 40, 0.06)',
      },
      fontFamily: {
        sans: [
          'Inter',
          'SF Pro Display',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
      },
      maxWidth: {
        content: '1480px',
      },
    },
  },
  plugins: [],
};
