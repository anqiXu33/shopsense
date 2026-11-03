import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 127.0.0.1, not localhost: Node may resolve localhost to IPv6 ::1,
      // where uvicorn (bound to 127.0.0.1) is not listening.
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
