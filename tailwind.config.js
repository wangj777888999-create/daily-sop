/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'page-bg': '#F7F3EC',
        'sidebar-bg': '#EDE7D9',
        'ai-panel-bg': '#EAE4D6',
        'topbar-bg': '#FEFCF8',
        'card-bg': '#FEFCF8',
        'card-gradient': '#F5EFE5',
        'border': '#C4BAA8',
        'text-heading': '#3D3530',
        'text-body': '#6B5F52',
        'text-light': '#9C8E82',
        'accent': '#5B8F7A',
        'accent-dark': '#4E7D6A',
        'accent-light': '#D6EDE7',
        'amber': '#C17F3A',
        'blue': '#3A7FC1',
        'purple': '#7B6BAA',
        'placeholder': '#DDD6C8',
        'placeholder-dk': '#C8BFB0',
        'chip': '#E5DDD0',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"PingFang SC"', '"Microsoft YaHei"', 'sans-serif'],
      },
      fontSize: {
        'title-lg': ['20px', { fontWeight: '700', lineHeight: '1.3' }],
        'title-md': ['16px', { fontWeight: '700', lineHeight: '1.4' }],
        'title-sm': ['14px', { fontWeight: '700', lineHeight: '1.4' }],
        'body': ['13px', { fontWeight: '400', lineHeight: '1.5' }],
        'helper': ['12px', { fontWeight: '400', lineHeight: '1.5' }],
        'label': ['11px', { fontWeight: '400', lineHeight: '1.5' }],
        'micro': ['10px', { fontWeight: '700', lineHeight: '1.4', letterSpacing: '1px' }],
      },
      spacing: {
        'xs': '4px',
        'sm': '8px',
        'md': '12px',
        'lg': '14px',
        'xl': '20px',
      },
      borderRadius: {
        'sm': '6px',
        'md': '8px',
        'lg': '10px',
        'xl': '12px',
      },
      width: {
        'sidebar': '220px',
        'ai-panel': '280px',
      },
      height: {
        'topbar': '52px',
      },
      boxShadow: {
        'card': '0 1px 3px rgba(61, 53, 48, 0.07), inset 0 1px 0 rgba(255,255,255,0.75)',
        'card-hover': '0 6px 20px rgba(61, 53, 48, 0.10), 0 1px 4px rgba(61,53,48,0.05)',
        'input-focus': '0 0 0 3px rgba(91, 143, 122, 0.18)',
        'nav-active': '0 2px 10px rgba(91, 143, 122, 0.30)',
        'button-primary': '0 1px 2px rgba(61,53,48,0.16), inset 0 1px 0 rgba(255,255,255,0.15)',
      },
      transitionTimingFunction: {
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
    },
  },
  plugins: [],
}
