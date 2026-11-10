import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import {
  getProfile,
  login as loginApi,
  loginByEmail as loginByEmailApi,
  logout as logoutApi,
} from '@/api/auth'
import { TOKEN_STORAGE_KEY, USER_STORAGE_KEY } from '@/utils/request'
import type { EmailLoginPayload, LoginPayload, LoginResponse, UserInfo, UserProfile } from '@/types/user'

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
 * token 与用户信息（含 roles / permissions）都持久化到 localStorage，
 * 刷新页面后由 restore() 还原，避免出现「有 token 但没用户信息」的白屏。
 *
 * 注意：permissions 只用于渲染菜单/按钮，真正的权限判定在后端每个接口上，
 * 前端即使被篡改也拿不到越权数据（见《明文密文说明》第五节）。
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(readStoredToken())
  const user = ref<UserInfo | null>(readStoredUser())

  const isAuthenticated = computed(() => token.value.length > 0)
  /** 顶栏展示用：昵称优先，其次用户名 */
  const displayName = computed(() => user.value?.nickname || user.value?.username || '同学')
  /** 当前用户拥有的权限标识集合 */
  const permissions = computed<string[]>(() => user.value?.permissions ?? [])
  /** 当前用户拥有的角色名称 */
  const roles = computed<string[]>(() => user.value?.roles ?? [])
  /** 是否系统管理员（管理员拥有全部权限） */
  const isAdmin = computed(() => roles.value.includes('系统管理员'))

  /**
   * 判断是否有某个权限；不传 key 视为「不需要权限」。
   * 只用于界面显隐，不能作为安全边界。
   */
  function hasPerm(permKey?: string | null): boolean {
    if (!permKey) return true
    if (isAdmin.value) return true
    return permissions.value.includes(permKey)
  }

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

  /** 登录 / 验证码登录成功后统一落库：token + 用户 + 角色 + 权限 */
  function applyLogin(res: LoginResponse): void {
    setToken(res.access_token)
    setUser({
      ...res.user,
      roles: res.roles ?? [],
      permissions: res.permissions ?? [],
    })
  }

  /** 用户名 + 密码登录 */
  async function login(payload: LoginPayload): Promise<void> {
    applyLogin(await loginApi(payload))
  }

  /** 邮箱验证码登录 */
  async function loginByEmail(payload: EmailLoginPayload): Promise<void> {
    applyLogin(await loginByEmailApi(payload))
  }

  /** 拉取最新资料，同时把角色/权限同步到本地缓存 */
  async function fetchProfile(): Promise<UserProfile | null> {
    if (!isAuthenticated.value) return null
    const profile = await getProfile()
    setUser({
      id: profile.id,
      username: profile.username,
      email: profile.email,
      nickname: profile.nickname,
      display_name: profile.display_name,
      roles: profile.roles,
      permissions: profile.permissions,
    })
    return profile
  }

  /** 退出登录：先通知后端吊销令牌，再清空本地状态 */
  async function logout(): Promise<void> {
    try {
      if (isAuthenticated.value) {
        await logoutApi()
      }
    } catch {
      // 令牌可能已过期，接口失败也要把本地状态清干净
    } finally {
      reset()
    }
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
    permissions,
    roles,
    isAdmin,
    isAuthenticated,
    displayName,
    hasPerm,
    setToken,
    setUser,
    reset,
    login,
    loginByEmail,
    fetchProfile,
    logout,
    restore,
  }
})
