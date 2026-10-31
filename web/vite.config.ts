import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // In dev, /api goes to the FastAPI server. In production nginx does the same (web/nginx.conf).
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
