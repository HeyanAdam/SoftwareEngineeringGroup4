/**
 * 认证状态: 令牌 / 用户资料 / 权限点。
 * 令牌持久化在 localStorage, 刷新页面后可通过 hydrate() 恢复会话。
 */

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import * as authApi from '@/api/auth'
import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setRememberedUsername,
  setTokens,
} from '@/utils/storage'
import { hasPermission, hasRole } from '@/utils/permission'
import type { CurrentUser, LoginPayload, ProfileUpdatePayload, RegisterPayload } from '@/types/auth'
import type { NormalizedApiError } from '@/types/common'

export const useAuthStore = defineStore('auth', () => {
  /* ------------------------------- state ------------------------------- */
  const accessToken = ref<string | null>(getAccessToken())
  const refreshToken = ref<string | null>(getRefreshToken())
  const user = ref<CurrentUser | null>(null)
  /** 是否已经尝试过拉取用户资料 (路由守卫依赖) */
  const hydrated = ref(false)
  const loading = ref(false)

  /* ------------------------------ getters ------------------------------ */
  const isAuthenticated = computed(() => Boolean(accessToken.value))
  const permissions = computed<string[]>(() => user.value?.permissions ?? [])
  const roles = computed<string[]>(() => user.value?.roles ?? [])
  const isSuperuser = computed(() => user.value?.is_superuser ?? false)
  const displayName = computed(
    () => user.value?.full_name || user.value?.username || '未登录',
  )

  /* ------------------------------ actions ------------------------------ */

  /** 写入令牌并同步内存状态 */
  function applyTokens(tokens: {
    access_token: string
    refresh_token: string
    expires_in: number
    token_type: string
  }): void {
    setTokens(tokens)
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
  }

  /** 清空令牌与用户信息 */
  function reset(): void {
    clearTokens()
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    hydrated.value = true
  }

  /**
   * 登录。
   * @param payload 用户名/邮箱 + 密码
   * @param remember 是否记住用户名 (仅记住用户名, 不保存密码)
   */
  async function login(payload: LoginPayload, remember = false): Promise<CurrentUser> {
    loading.value = true
    try {
      const tokens = await authApi.login(payload)
      applyTokens(tokens)
      setRememberedUsername(remember ? payload.username : '')
      const profile = await authApi.getMe()
      user.value = profile
      hydrated.value = true
      return profile
    } finally {
      loading.value = false
    }
  }

  /** 注册 (不自动登录) */
  async function register(payload: RegisterPayload): Promise<CurrentUser> {
    return authApi.register(payload)
  }

  /** 拉取当前用户资料与权限点 */
  async function fetchProfile(): Promise<CurrentUser | null> {
    if (!accessToken.value) return null
    const profile = await authApi.getMe()
    user.value = profile
    hydrated.value = true
    return profile
  }

  /** 刷新令牌 (refresh_token 轮换, 必须保存新的) */
  async function refreshSession(): Promise<string | null> {
    const current = refreshToken.value
    if (!current) return null
    const tokens = await authApi.refresh({ refresh_token: current })
    applyTokens(tokens)
    return tokens.access_token
  }

  /**
   * 路由守卫使用: 首次进入应用时恢复会话。
   * 失败时保持未登录状态 (不抛出, 避免导航被中断)。
   */
  async function hydrate(): Promise<void> {
    if (hydrated.value) return
    if (!accessToken.value) {
      hydrated.value = true
      return
    }
    try {
      await fetchProfile()
    } catch (error) {
      const status = (error as NormalizedApiError | undefined)?.status
      // 401 已由拦截器处理 (清令牌 + 跳登录); 其他错误保留令牌以便重试
      if (status === 401) reset()
    } finally {
      hydrated.value = true
    }
  }

  /** 更新个人资料 */
  async function updateProfile(payload: ProfileUpdatePayload): Promise<CurrentUser> {
    const profile = await authApi.updateMe(payload)
    user.value = profile
    return profile
  }

  /** 修改密码 (成功后后端会使旧令牌失效, 前端需重新登录) */
  async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await authApi.changePassword({ old_password: oldPassword, new_password: newPassword })
  }

  /** 退出登录: 通知后端使令牌失效, 本地无论成败都清理 */
  async function logout(): Promise<void> {
    try {
      if (accessToken.value) await authApi.logout()
    } catch {
      // 退出接口失败不阻塞本地清理
    } finally {
      reset()
    }
  }

  /** 权限判定 (含超管与 module:* 通配) */
  function checkPermission(required: string | string[] | null | undefined): boolean {
    return hasPermission(permissions.value, required, isSuperuser.value)
  }

  /** 角色判定 */
  function checkRole(required: string | string[] | null | undefined): boolean {
    return hasRole(roles.value, required, isSuperuser.value)
  }

  return {
    // state
    accessToken,
    refreshToken,
    user,
    hydrated,
    loading,
    // getters
    isAuthenticated,
    permissions,
    roles,
    isSuperuser,
    displayName,
    // actions
    applyTokens,
    reset,
    login,
    register,
    fetchProfile,
    refreshSession,
    hydrate,
    updateProfile,
    changePassword,
    logout,
    checkPermission,
    checkRole,
  }
})
