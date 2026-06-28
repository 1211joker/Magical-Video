import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 300000,  // 5 分钟，SSE 长连接 + AI 分析大文本需要较长时间
        proxyTimeout: 300000,
      }
    }
  }
})
