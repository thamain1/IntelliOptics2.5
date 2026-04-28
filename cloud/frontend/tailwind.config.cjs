/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // 4wardmotion brand tokens. Source of truth: 4wardmotion-site/src/sections/Hero.tsx
        brand: {
          bg:        '#0a0f08',
          bg2:       '#11180e',
          primary:   '#90C226',
          primaryH:  '#54A021',
          sage:      '#B9D181',
          text:      '#f1f5f9',
          textDim:   '#94a3b8',
          line:      'rgba(144, 194, 38, 0.2)',
          panel:     'rgba(144, 194, 38, 0.05)',
        },
      },
      fontFamily: {
        display: ['Oswald', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
      },
      letterSpacing: {
        ioWide: '0.18em',
        ioWider: '0.3em',
      },
    },
  },
  plugins: [],
};
