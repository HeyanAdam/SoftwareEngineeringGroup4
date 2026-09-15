/**
 * Vitest 配置 (jsdom 环境, 覆盖 src/**\/*.spec.ts)
 *
 * 单测只跑纯逻辑与轻量组件, 不依赖真实后端; 需要请求时在用例里 mock `@/api/*`。
 */
import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [
    vue({
      template: { compilerOptions: { expressionPlugins: ['typescript'] } },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    // jsdom 提供 document / window / localStorage
    environment: 'jsdom',
    include: ['src/**/*.spec.ts'],
    globals: false,
    css: false,
    restoreMocks: true,
    server: {
      deps: {
        // Element Plus 以 ESM 提供, 直接内联可避免 CJS 互操作问题
        inline: ['element-plus'],
      },
    },
  },
})
