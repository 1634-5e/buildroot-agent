import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    proxy: {
      // 代理 API 到 Rust Server
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      // 代理 WebSocket 到 Rust Server (Phase 1: DeviceList, Phase 2: PTY)
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})