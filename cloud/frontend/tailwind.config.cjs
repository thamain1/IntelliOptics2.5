/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // 4wardmotion brand tokens.
        // bg2 lifted from #11180e -> #1a2316 (2026-04-28) so panels/cards
        // visibly separate from the canvas. Original #11180e was only ~3 RGB
        // points off bg, leaving cards invisible on dashboard pages.
        // line opacity raised 0.2 -> 0.35 for clearer card edges.
        brand: {
          bg:        '#0a0f08',
          bg2:       '#1a2316',
          primary:   '#90C226',
          primaryH:  '#54A021',
          sage:      '#B9D181',
          text:      '#f1f5f9',
          textDim:   '#94a3b8',
          line:      'rgba(144, 194, 38, 0.35)',
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
