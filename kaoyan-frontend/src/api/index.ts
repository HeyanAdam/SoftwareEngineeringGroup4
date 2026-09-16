/**
 * 接口统一出口。
 * 既可以直接 `import { login } from '@/api/auth'`，也可以：
 * `import { authApi, chatApi, planApi } from '@/api'`
 */
export * as authApi from './auth'
export * as chatApi from './chat'
export * as planApi from './plan'
