/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        border: '#E5EAF2',
        line: '#CED7E5',
        input: '#DDE5EF',
        ring: '#586AD9',
        background: '#F7F9FC',
        foreground: '#1C273B',
        primary: {
          DEFAULT: '#586AD9',
          hover: '#4B5DC5',
          foreground: '#FFFFFF',
          soft: '#EDF0FF',
        },
        brand: {
          DEFAULT: '#4E70BE',
          soft: '#EAF2FF',
          foreground: '#FFFFFF',
        },
        secondary: {
          DEFAULT: '#F2F5FA',
          foreground: '#1C273B',
        },
        muted: {
          DEFAULT: '#F2F5FA',
          foreground: '#68778D',
        },
        accent: {
          DEFAULT: '#EDF0FF',
          foreground: '#4B5DC5',
        },
        destructive: {
          DEFAULT: '#B95252',
          foreground: '#FFFFFF',
          soft: '#FCEBEC',
        },
        success: {
          DEFAULT: '#287F61',
          foreground: '#FFFFFF',
          soft: '#E8F7F0',
        },
        warning: {
          DEFAULT: '#99661E',
          foreground: '#FFFFFF',
          soft: '#FFF4E2',
        },
        info: {
          DEFAULT: '#4E70BE',
          foreground: '#FFFFFF',
          soft: '#EAF2FF',
        },
        aqua: {
          DEFAULT: '#1F6A6A',
          soft: '#E8F7F7',
        },
        pink: {
          soft: '#F0ECFA',
          DEFAULT: '#6E62A8',
        },
        card: {
          DEFAULT: '#FFFFFF',
          foreground: '#1C273B',
        },
        nav: {
          DEFAULT: '#172F4B',
          hover: '#2A425C',
          active: '#2C73DA',
          bright: '#F6FAFF',
          text: '#B6C9DE',
          label: '#829EBC',
          divider: 'rgba(255, 255, 255, 0.12)',
          shade: '#0D1E35',
          avatar: '#E2EEFF',
          ink: '#244B7F',
        },
      },
      borderRadius: {
        xl: '18px',
        lg: '14px',
        md: '10px',
        sm: '8px',
      },
      boxShadow: {
        card: '0 2px 7px rgba(31, 49, 82, 0.045)',
        soft: '0 12px 32px rgba(36, 59, 105, 0.08)',
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Arial',
          'sans-serif',
        ],
      },
      maxWidth: {
        content: '1680px',
      },
    },
  },
  plugins: [],
};
