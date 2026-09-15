/**
 * 本地存储封装: 令牌与"记住我"用户名。
 * 统一加 sg4: 前缀, 并对 localStorage 不可用 (隐私模式 / SSR) 做降级。
 */

import type { TokenPair } from '@/types/auth'

const PREFIX = 'sg4:'

export const StorageKey = {
  accessToken: `${PREFIX}access_token`,
  refreshToken: `${PREFIX}refresh_token`,
  /** access_token 过期时间戳 (毫秒) */
  expiresAt: `${PREFIX}expires_at`,
  /** 记住的用户名 (登录页回填) */
  rememberUsername: `${PREFIX}remember_username`,
  /** 主题模式 light | dark */
  theme: `${PREFIX}theme`,
  /** 侧边栏是否折叠 */
  sidebarCollapsed: `${PREFIX}sidebar_collapsed`,
} as const

export type StorageKeyName = (typeof StorageKey)[keyof typeof StorageKey]

/** localStorage 是否可用 (SSR / 隐私模式下可能抛异常) */
function getStorage(): Storage | null {
  try {
    if (typeof window === 'undefined' || !window.localStorage) return null
    return window.localStorage
  } catch {
    return null
  }
}

/** 读取字符串 */
export function getItem(key: StorageKeyName): string | null {
  return getStorage()?.getItem(key) ?? null
}

/** 写入字符串 */
export function setItem(key: StorageKeyName, value: string): void {
  getStorage()?.setItem(key, value)
}

/** 删除键 */
export function removeItem(key: StorageKeyName): void {
  getStorage()?.removeItem(key)
}

/** 读取布尔值 */
export function getBoolean(key: StorageKeyName): boolean {
  return getItem(key) === 'true'
}

/** 写入布尔值 */
export function setBoolean(key: StorageKeyName, value: boolean): void {
  setItem(key, value ? 'true' : 'false')
}

/** 读取并反序列化 JSON */
export function getJson<T>(key: StorageKeyName, fallback: T): T {
  const raw = getItem(key)
  if (!raw) return fallback
  try {
    return JSON.parse(raw) as T
  } catch {
    return fallback
  }
}

/** 序列化写入 JSON */
export function setJson(key: StorageKeyName, value: unknown): void {
  setItem(key, JSON.stringify(value))
}

/* ------------------------------- 令牌 ------------------------------- */

/** 读取 access_token */
export function getAccessToken(): string | null {
  return getItem(StorageKey.accessToken)
}

/** 读取 refresh_token */
export function getRefreshToken(): string | null {
  return getItem(StorageKey.refreshToken)
}

/** 持久化令牌对; refresh_token 每次刷新都会轮换, 必须整体覆盖写入 */
export function setTokens(tokens: TokenPair): void {
  setItem(StorageKey.accessToken, tokens.access_token)
  setItem(StorageKey.refreshToken, tokens.refresh_token)
  setItem(StorageKey.expiresAt, String(Date.now() + tokens.expires_in * 1000))
}

/** 清空令牌 */
export function clearTokens(): void {
  removeItem(StorageKey.accessToken)
  removeItem(StorageKey.refreshToken)
  removeItem(StorageKey.expiresAt)
}

/** access_token 是否已过期 (留 30s 安全边界) */
export function isAccessTokenExpired(skewMs = 30_000): boolean {
  const raw = getItem(StorageKey.expiresAt)
  if (!raw) return false
  const expiresAt = Number(raw)
  if (!Number.isFinite(expiresAt)) return false
  return Date.now() >= expiresAt - skewMs
}

/* --------------------------- 记住我用户名 --------------------------- */

/** 读取记住的用户名 */
export function getRememberedUsername(): string | null {
  return getItem(StorageKey.rememberUsername)
}

/** 记住 / 取消记住用户名 (传空字符串即清除) */
export function setRememberedUsername(username: string): void {
  if (username) {
    setItem(StorageKey.rememberUsername, username)
  } else {
    removeItem(StorageKey.rememberUsername)
  }
}

/** 清空本应用写入的全部键 (退出登录时使用, 保留记住的用户名) */
export function clearSession(): void {
  clearTokens()
}
