import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy /api/* to the FastAPI backend so we never hardcode a port.
      // The frontend calls fetch('/api/optimize') and Vite forwards it to
      // http://localhost:8000/api/optimize during development.
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
