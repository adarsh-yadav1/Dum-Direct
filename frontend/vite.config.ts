import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    // In development the page and the API share one address, as they do in production,
    // so sign-in cookies behave the same way. Run the API with: uvicorn app.site:site
    proxy: { '/api': 'http://localhost:8000' },
  },
})
