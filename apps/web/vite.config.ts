import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      // Backend that (services/backend) chay local o 127.0.0.1:8001, API
      // path bat dau /api/local/v1 (xem src/api.ts cua nhanh
      // chore/w1-w11-evidence-integration da merge vao main) -- proxy nay
      // CHUA duoc dung boi lib/api.ts hien tai (van con mock), se dung
      // khi thay the tung ham mock bang fetch() that.
      '/api/local/v1': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: false,
      },
    },
  },
})
