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
      // Backend that (services/backend, nhanh feat/w3-mongo-auth-app cua
      // Quy da merge vao) dung dung path /api/v1 theo API_CONTRACT_V1.md,
      // chay local o 127.0.0.1:8001 -- day moi la path lib/api.ts se goi
      // khi thay mock bang fetch() that.
      '/api/v1': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: false,
      },
      // Demo offline rieng (src/api.ts, khong lien quan UI hien tai).
      '/api/local/v1': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: false,
      },
    },
  },
})
