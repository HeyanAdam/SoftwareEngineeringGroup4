import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { getProfile, login as loginApi } from '@/api/auth'
import { TOKEN_STORAGE_KEY, USER_STORAGE_KEY } from '@/utils/request'
import type { LoginPayload, UserInfo, UserProfile } from '@/types/user'

/** 从 localStorage 还原用户信息，解析失败返回 null */
function readStoredUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      return parsed as UserInfo
    }
    return null
  } catch {
    return null
  }
}

/** 读取本地 token（refresh 时也会用到） */
function readStoredToken(): string {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

/**
 * 登录态 store：
 * token 与用户信息都持久化到 localStorage，
 * 刷新页面后由 restore() 还原，避免出现「有 token 但没用户信息」的白屏。
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(readStoredToken())
  const user = ref<UserInfo | null>(readStoredUser())

  const isAuthenticated = computed(() => token.value.length > 0)
  /** 顶栏展示用：昵称优先，其次用户名 */
  const displayName = computed(() => user.value?.nickname || user.value?.username || '同学')

  /** 写入 token 并持久化 */
  function setToken(value: string): void {
    token.value = value
    try {
      localStorage.setItem(TOKEN_STORAGE_KEY, value)
    } catch {
      // 忽略 localStorage 不可用的情况
    }
  }

  /** 写入用户信息并持久化 */
  function setUser(value: UserInfo | null): void {
    user.value = value
    try {
      if (value) {
        localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(value))
      } else {
        localStorage.removeItem(USER_STORAGE_KEY)
      }
    } catch {
      // 忽略 localStorage 不可用的情况
    }
  }

  /** 清空登录态（401 或主动退出登录时调用） */
  function reset(): void {
    token.value = ''
    setUser(null)
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    } catch {
      // 忽略 localStorage 不可用的情况
    }
  }

  /** 登录：保存 token 与用户信息 */
  async function login(payload: LoginPayload): Promise<void> {
    const res = await loginApi(payload)
    setToken(res.access_token)
    setUser(res.user)
  }

  /** 拉取最新资料，同时把昵称等字段同步到本地缓存 */
  async function fetchProfile(): Promise<UserProfile | null> {
    if (!isAuthenticated.value) return null
    const profile = await getProfile()
    setUser({
      id: profile.id,
      username: profile.username,
      email: profile.email,
      nickname: profile.nickname,
    })
    return profile
  }

  /** 页面刷新后调用：token 已在初始化时还原，这里只补齐用户信息 */
  async function restore(): Promise<void> {
    if (!isAuthenticated.value || user.value) return
    try {
      await fetchProfile()
    } catch {
      // 拉取失败（例如后端未启动）不阻塞页面，401 已由拦截器统一处理
    }
  }

  return {
    token,
    user,
    isAuthenticated,
    displayName,
    setToken,
    setUser,
    reset,
    login,
    fetchProfile,
    restore,
  }
})
