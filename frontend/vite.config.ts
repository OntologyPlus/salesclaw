import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
    // 局域网可访问：监听所有接口（开发用）
    host: true,
    // 允许所有主机请求（HMR / CORS）
    strictPort: false,
    proxy: {
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
