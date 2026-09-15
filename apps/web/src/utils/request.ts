/**
 * Axios 实例与拦截器。
 *
 * 约定 (与后端一致):
 *  - 请求: baseURL = import.meta.env.VITE_API_BASE_URL (默认 /api/v1), 15s 超时
 *  - 成功: 直接返回 response.data (业务层拿到的是纯资源)
 *  - 失败: HTTP status + JSON { code, message, data? }; 统一弹出 ElMessage
 *  - 401 + code ∈ {40101, 40102, 40107, 40100}: 单飞 (single-flight) 刷新令牌,
 *    并发 401 排队重试; 刷新失败则清空令牌并跳转 /login?redirect=...
 */

import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios'
import { ElMessage } from 'element-plus'

import { clearTokens, getAccessToken, getRefreshToken, setTokens } from '@/utils/storage'
import type { ApiErrorBody, NormalizedApiError } from '@/types/common'
import type { TokenPair } from '@/types/auth'

/** 需要触发刷新令牌的业务码 */
const REFRESHABLE_CODES = new Set([40100, 40101, 40102, 40107])

/** 该请求是否跳过全局错误提示 */
export interface RequestOptions extends AxiosRequestConfig {
  silent?: boolean
}

/** 用于标记"已经重试过一次"的请求配置, 防止无限循环 */
interface RetriableConfig extends RequestOptions {
  _retried?: boolean
}

/** 各 HTTP 状态的兜底文案 */
const STATUS_TEXT: Record<number, string> = {
  400: '请求参数不正确',
  401: '登录状态已失效, 请重新登录',
  403: '没有权限执行该操作',
  404: '请求的资源不存在',
  409: '数据冲突, 请刷新后重试',
  413: '文件体积超过限制',
  422: '参数校验失败',
  429: '请求过于频繁, 请稍后再试',
  500: '服务器内部错误',
  502: '网关/依赖服务异常',
  503: '服务暂时不可用',
}

/**
 * 应用层 HTTP 客户端: 响应拦截器已把 AxiosResponse 解包为业务数据,
 * 因此方法签名直接返回 Promise<T>。
 */
export interface HttpClient {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T>
  request<T>(config: AxiosRequestConfig): Promise<T>
}

const AUTH_ENDPOINTS = {
  refresh: '/auth/refresh',
  login: '/auth/login',
} as const

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

/** 当前是否已经在刷新令牌 (单飞) */
let refreshing = false
/** 等待刷新结果的并发请求队列 */
let waiters: Array<(token: string | null) => void> = []

const raw = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
})

/** 对外暴露的已解包客户端 */
const service = raw as unknown as HttpClient

raw.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken()
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`)
    }
    return config
  },
  (error: unknown) => Promise.reject(error),
)

/** 把任意异常归一化成带 status / code / message 的对象 */
export function normalizeError(error: unknown): NormalizedApiError {
  const axiosError = error as AxiosError<ApiErrorBody>
  const status = axiosError?.response?.status ?? 0
  const body = axiosError?.response?.data
  const code = typeof body?.code === 'number' ? body.code : status * 100
  let message = typeof body?.message === 'string' && body.message ? body.message : ''

  if (!message) {
    if (axiosError?.code === 'ECONNABORTED' || axiosError?.code === 'ETIMEDOUT') {
      message = '请求超时, 请检查网络后重试'
    } else if (axiosError?.code === 'ERR_NETWORK') {
      message = '网络异常, 无法连接服务器'
    } else {
      message = STATUS_TEXT[status] ?? '请求失败, 请稍后重试'
    }
  }

  return { status, code, message, data: body?.data }
}

/** 跳转登录页并带上回跳地址 */
function redirectToLogin(): void {
  if (typeof window === 'undefined') return
  const { pathname, search, hash } = window.location
  if (pathname === '/login') return
  const redirect = encodeURIComponent(`${pathname}${search}${hash}`)
  // 使用 replace 避免用户点后退又回到已失效的页面
  window.location.replace(`/login?redirect=${redirect}`)
}

/**
 * 单飞刷新: 并发 401 只发一次 /auth/refresh。
 * 刷新成功后落库新的 refresh_token (后端会轮换, 旧的立即失效)。
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return null

  try {
    const { data } = await axios.post<TokenPair>(
      `${API_BASE_URL}${AUTH_ENDPOINTS.refresh}`,
      { refresh_token: refreshToken },
      { timeout: 15_000, headers: { 'Content-Type': 'application/json' } },
    )
    setTokens(data)
    return data.access_token
  } catch {
    return null
  }
}

/** 触发一次刷新, 并把结果广播给排队的请求 */
function startRefreshFlow(): Promise<string | null> {
  if (refreshing) {
    return new Promise<string | null>((resolve) => {
      waiters.push(resolve)
    })
  }

  refreshing = true
  return refreshAccessToken()
    .then((token) => {
      const queued = waiters
      waiters = []
      for (const resolve of queued) resolve(token)
      return token
    })
    .finally(() => {
      refreshing = false
    })
}

/** 判断该请求是否可刷新重试 */
function canRefresh(config: RetriableConfig | undefined): boolean {
  if (!config || config._retried) return false
  const url = config.url ?? ''
  // 登录 / 刷新接口自身的 401 不再触发刷新
  if (url.includes(AUTH_ENDPOINTS.refresh) || url.includes(AUTH_ENDPOINTS.login)) return false
  return Boolean(getRefreshToken())
}

/** 处理 401: 刷新 + 重试, 或清理令牌并跳转登录 */
async function handleUnauthorized(
  config: RetriableConfig | undefined,
  normalized: NormalizedApiError,
): Promise<never> {
  const shouldRefresh =
    normalized.status === 401 || REFRESHABLE_CODES.has(normalized.code)

  if (shouldRefresh && canRefresh(config) && config) {
    const token = await startRefreshFlow()
    if (token) {
      config._retried = true
      const headers = { ...(config.headers ?? {}) } as Record<string, string>
      headers.Authorization = `Bearer ${token}`
      // 重放原请求 (拦截器签名已解包, 这里声明为 AxiosResponse)
      return raw.request({ ...config, headers }) as unknown as Promise<never>
    }
  }

  clearTokens()
  ElMessage.closeAll()
  ElMessage.error(normalized.message || STATUS_TEXT[401]!)
  redirectToLogin()
  return Promise.reject(normalized)
}

raw.interceptors.response.use(
  (response: AxiosResponse) => response.data as never,
  async (error: AxiosError<ApiErrorBody>) => {
    const normalized = normalizeError(error)
    const config = error.config as RetriableConfig | undefined
    const url = config?.url ?? ''

    // 刷新接口自身的失败直接透传, 由调用方决定行为
    if (url.includes(AUTH_ENDPOINTS.refresh)) {
      return Promise.reject(normalized)
    }

    if (normalized.status === 401) {
      return handleUnauthorized(config, normalized)
    }

    if (!config?.silent) {
      ElMessage.error(normalized.message)
    }
    return Promise.reject(normalized)
  },
)

/** GET, 返回已解包的业务数据 */
export function get<T>(
  url: string,
  params?: Record<string, unknown>,
  options?: RequestOptions,
): Promise<T> {
  return service.get<T>(url, { params, ...options })
}

/** POST */
export function post<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
  return service.post<T>(url, data, options)
}

/** PUT */
export function put<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
  return service.put<T>(url, data, options)
}

/** PATCH */
export function patch<T>(url: string, data?: unknown, options?: RequestOptions): Promise<T> {
  return service.patch<T>(url, data, options)
}

/** DELETE */
export function del<T>(url: string, options?: RequestOptions): Promise<T> {
  return service.delete<T>(url, options)
}

/** 上传 multipart 表单 (不覆盖 Content-Type, 让浏览器带 boundary) */
export function upload<T>(
  url: string,
  formData: FormData,
  options?: RequestOptions,
  onProgress?: (percent: number) => void,
): Promise<T> {
  return service.post<T>(url, formData, {
    timeout: 120_000,
    ...options,
    headers: { ...options?.headers },
    onUploadProgress: (event) => {
      if (!onProgress) return
      const total = event.total ?? 0
      if (total > 0) onProgress(Math.round((event.loaded / total) * 100))
    },
  })
}

export { service as httpClient }
