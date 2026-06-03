import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Target del proxy /api configurable por env:
//   - Dev nativo (Windows): default `localhost:18000` — el puerto 8000 está
//     reservado por Hyper-V port exclusions, ver `backend/README.md`.
//   - Docker compose: `VITE_PROXY_TARGET=http://backend:8000` (servicio compose).
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:18000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  envDir: path.resolve(__dirname, '..'),
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
