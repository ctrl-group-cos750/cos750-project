import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Two pages: the app, and the UI kit reference at /ui-kit.html.
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('index.html', import.meta.url)),
        uiKit: fileURLToPath(new URL('ui-kit.html', import.meta.url)),
      },
    },
  },
  server: {
    // In dev, /api goes to the FastAPI server. In production nginx does the same (web/nginx.conf).
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/ui-kit/main.tsx', 'src/test/**'],
    },
  },
})
