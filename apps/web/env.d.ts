/// <reference types="vite/client" />

/** 应用级环境变量 (与 .env.* 文件一一对应) */
interface ImportMetaEnv {
  /** REST 基础地址, 默认 /api/v1 */
  readonly VITE_API_BASE_URL?: string
  /** WebSocket 基础地址, 默认 /ws */
  readonly VITE_WS_BASE_URL?: string
  /** 浏览器标题 / 控制台名称 */
  readonly VITE_APP_TITLE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}
