import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for the IntelliOptics frontend.
// This config enables React and TypeScript support and proxies API
// requests to the backend during development.

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/detectors': 'http://localhost:8000',
      '/queries': 'http://localhost:8000',
      '/escalations': 'http://localhost:8000',
      '/hubs': 'http://localhost:8000',
      '/token': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/demo-streams': 'http://localhost:8000',
      '/deployments': 'http://localhost:8000',
      '/inspection-config': 'http://localhost:8000',
      '/camera-inspection': 'http://localhost:8000',
      '/detector-alerts': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/settings': 'http://localhost:8000',
    },
  },
});