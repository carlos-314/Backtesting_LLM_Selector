import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// Target del proxy /api configurable por env:
//   - Dev nativo (Windows): default `127.0.0.1:18000` (IPv4 explícito).
//     uvicorn escucha solo en IPv4 por defecto; Node 18+ resuelve `localhost`
//     a `::1` (IPv6) y la conexión sería rechazada (ECONNREFUSED).
//     El puerto 8000 está reservado por Hyper-V port exclusions
//     (ver `backend/README.md`).
//   - Docker compose: `VITE_PROXY_TARGET=http://backend:8000` (servicio compose).
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:18000'

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
