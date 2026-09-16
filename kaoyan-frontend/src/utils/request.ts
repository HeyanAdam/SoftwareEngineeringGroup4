import axios, { AxiosError } from 'axios'
import type { AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

/** token 在 localStorage 中的键名（auth store 持久化时使用同一个键） */
export const TOKEN_STORAGE_KEY = 'kaoyan_token'

/** 用户信息在 localStorage 中的键名（401 清理登录态时一并清除） */
export const USER_STORAGE_KEY = 'kaoyan_user'

/** 未登录 / token 过期时跳转的登录页路径 */
const LOGIN_PATH = '/login'

/** 后端失败响应体（宽松版：message 缺失时不影响提示逻辑） */
interface ErrorResponseBody {
  code?: number
  message?: string
  data?: null
}

/** 业务/网络层统一异常类型，避免调用方拿到 any */
export class RequestError extends Error {
  /** 业务错误码：优先取响应体 code，否则回退为 HTTP 状态码 */
  readonly code: number
  /** HTTP 状态码；网络错误或超时时为 0 */
  readonly status: number

  constructor(message: string, code: number, status: number) {
    super(message)
    this.name = 'RequestError'
    this.code = code
    this.status = status
  }
}

/**
 * 读取本地 token。
 * 这里直接读 localStorage 而不是注入 Pinia store，原因有二：
 * 1) 避免 utils -> stores -> api -> utils 的循环依赖；
 * 2) 避免请求拦截器在 Pinia 尚未初始化时被调用而报错。
 * auth store 用同一个键做持久化，两者始终一致。
 */
function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    // 隐私模式等场景下 localStorage 可能不可用
    return null
  }
}

/** 401 时清理登录态并跳转登录页（带上 redirect 便于登录后跳回） */
function handleUnauthorized(): void {
  try {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    localStorage.removeItem(USER_STORAGE_KEY)
  } catch {
    // 忽略 localStorage 不可用
  }

  ElMessage.error('登录状态已过期，请重新登录')

  const { pathname, search, hash } = window.location
  // 已经在登录页就不再跳转，避免重复跳转 / 死循环
  if (pathname === LOGIN_PATH) return

  const redirect = encodeURIComponent(`${pathname}${search}${hash}`)
  window.location.replace(`${LOGIN_PATH}?redirect=${redirect}`)
}

/** 根据 HTTP 状态码给出兜底中文提示（后端没返回 message 时使用） */
function fallbackMessageByStatus(status: number): string {
  if (status === 400) return '请求参数有误'
  if (status === 401) return '登录状态已过期，请重新登录'
  if (status === 403) return '没有访问权限'
  if (status === 404) return '请求的资源不存在'
  if (status >= 500) return '服务器开小差了，请稍后再试'
  return '请求失败'
}

/** 把 axios 抛出的异常转换成可读的中文提示 */
function resolveErrorMessage(error: AxiosError<ErrorResponseBody>): string {
  const response = error.response
  if (response) {
    const body = response.data
    if (body && typeof body.message === 'string' && body.message.length > 0) {
      return body.message
    }
    return fallbackMessageByStatus(response.status)
  }
  if (error.code === 'ECONNABORTED') {
    return '请求超时，请检查网络后重试'
  }
  return '网络异常，请稍后重试'
}

/** 请求实例：baseURL 为 /api，开发环境由 Vite 代理转发到后端 */
const instance = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截器：有 token 就带上 Authorization 头
instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：成功直接把 data 交给业务代码；失败统一提示并抛出 RequestError
instance.interceptors.response.use(
  // 运行时这里返回的已经是 response.data，但 axios 的类型签名只约束参数，
  // 调用侧的类型安全由下面 request.get<T>() 等泛型方法保证。
  (response: AxiosResponse) => response.data,
  (error: AxiosError<ErrorResponseBody>) => {
    const message = resolveErrorMessage(error)
    const status = error.response?.status ?? 0
    if (status === 401) {
      handleUnauthorized()
    } else {
      ElMessage.error(message)
    }
    const code = error.response?.data?.code ?? status
    return Promise.reject(new RequestError(message, code, status))
  },
)

/** 泛型请求对象：返回值直接是后端响应体数据 T */
export interface Request {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T>
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T>
}

/** 泛型请求函数：传入响应体类型即可获得精确的返回值类型 */
export function requestFn<T>(config: AxiosRequestConfig): Promise<T> {
  return instance.request<T, T>(config)
}

/**
 * 请求对象：提供语义化的泛型方法，供 src/api/* 使用。
 * 定义成接口（而不是在函数上挂属性）可以让每个方法的泛型签名完整保留。
 */
export const request: Request = {
  get: <T>(url: string, config?: AxiosRequestConfig): Promise<T> => instance.get<T, T>(url, config),
  post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
    instance.post<T, T>(url, data, config),
  put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
    instance.put<T, T>(url, data, config),
  patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> =>
    instance.patch<T, T>(url, data, config),
  delete: <T>(url: string, config?: AxiosRequestConfig): Promise<T> =>
    instance.delete<T, T>(url, config),
}

export default request
