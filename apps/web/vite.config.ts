import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

/** 后端开发服务地址, 与 apps/api 默认端口保持一致 */
const API_TARGET = process.env.VITE_DEV_API_TARGET ?? 'http://127.0.0.1:8000'

/** 开发服务器监听地址: 容器内开发需要 0.0.0.0 (可用 VITE_DEV_HOST 覆盖) */
const DEV_HOST = process.env.VITE_DEV_HOST ?? '127.0.0.1'
const DEV_PORT = Number(process.env.VITE_PORT ?? 5173)

export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // 模板表达式里允许 TS 语法 (如 `item as Foo`)
          expressionPlugins: ['typescript'],
        },
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: DEV_HOST,
    port: DEV_PORT,
    open: false,
    proxy: {
      // REST 接口 -> FastAPI
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      // WebSocket -> FastAPI (/ws?token=...)
      '/ws': {
        target: API_TARGET,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    target: 'es2020',
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        // 三方库拆包, 避免单个 chunk 过大 (ECharts 与 Element Plus 体积可观)
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (id.includes('echarts') || id.includes('zrender')) return 'echarts'
          if (id.includes('element-plus') || id.includes('@element-plus')) return 'element-plus'
          return 'vendor'
        },
      },
    },
  },
})
