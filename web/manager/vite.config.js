import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: './',  // Use relative paths so it works when served from /manager/
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
      // SimulatorView frames /sim/index.html, which the device manager serves
      // from web/sim. The dev server's root is web/manager, so without these
      // the iframe 404s in `npm run dev`. /icons is separate because the
      // simulator resolves its icon URLs relative to the site root.
      '/sim': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/icons': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
