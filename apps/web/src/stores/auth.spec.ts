/**
 * 认证 store 单元测试 (mock api 模块, 断言 localStorage 持久化与权限判定)
 */

import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import * as authApi from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { CurrentUser, TokenPair } from '@/types/auth'

// 只 mock 接口模块, store 内部的存储与权限逻辑走真实实现
vi.mock('@/api/auth')

const mockUser: CurrentUser = {
  id: 1,
  username: 'admin',
  email: 'admin@example.com',
  full_name: '超级管理员',
  avatar: null,
  phone: null,
  is_active: true,
  is_superuser: true,
  last_login_at: '2024-05-06T08:00:00Z',
  roles: ['super_admin'],
  permissions: ['users:read', 'users:write'],
}

const mockTokens: TokenPair = {
  access_token: 'access-token-1',
  refresh_token: 'refresh-token-1',
  token_type: 'bearer',
  expires_in: 3600,
}

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    window.localStorage.clear()
    vi.clearAllMocks()
  })

  it('初始状态为未登录', () => {
    const store = useAuthStore()
    expect(store.isAuthenticated).toBe(false)
    expect(store.permissions).toEqual([])
    expect(store.roles).toEqual([])
    expect(store.checkPermission('users:read')).toBe(false)
  })

  it('登录成功后持久化令牌并加载用户资料', async () => {
    vi.mocked(authApi.login).mockResolvedValue(mockTokens)
    vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

    const store = useAuthStore()
    const profile = await store.login({ username: 'admin', password: 'Admin@123456' }, true)

    expect(profile.username).toBe('admin')
    expect(store.isAuthenticated).toBe(true)
    expect(store.accessToken).toBe('access-token-1')
    expect(store.permissions).toEqual(['users:read', 'users:write'])
    expect(store.isSuperuser).toBe(true)
    expect(store.displayName).toBe('超级管理员')

    // 令牌落库 (access / refresh / 过期时间)
    expect(window.localStorage.getItem('sg4:access_token')).toBe('access-token-1')
    expect(window.localStorage.getItem('sg4:refresh_token')).toBe('refresh-token-1')
    expect(window.localStorage.getItem('sg4:expires_at')).toBeTruthy()
    // 记住我保存用户名 (不保存密码)
    expect(window.localStorage.getItem('sg4:remember_username')).toBe('admin')
  })

  it('未勾选记住我时不保存用户名', async () => {
    vi.mocked(authApi.login).mockResolvedValue(mockTokens)
    vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

    window.localStorage.setItem('sg4:remember_username', 'old-user')
    const store = useAuthStore()
    await store.login({ username: 'admin', password: 'Admin@123456' }, false)

    expect(window.localStorage.getItem('sg4:remember_username')).toBeNull()
  })

  it('权限与角色判定包含超管直通', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(mockUser)
    const store = useAuthStore()
    store.applyTokens(mockTokens)
    await store.fetchProfile()

    expect(store.checkPermission('users:read')).toBe(true)
    expect(store.checkPermission(['users:read', 'users:write'])).toBe(true)
    expect(store.checkRole('super_admin')).toBe(true)
    // 超管对未声明的权限也直通
    expect(store.checkPermission('system:monitor')).toBe(true)
  })

  it('退出登录会清理令牌与用户信息, 接口失败也不阻塞', async () => {
    vi.mocked(authApi.getMe).mockResolvedValue(mockUser)
    vi.mocked(authApi.logout).mockRejectedValue(new Error('network down'))

    const store = useAuthStore()
    store.applyTokens(mockTokens)
    await store.fetchProfile()
    expect(store.isAuthenticated).toBe(true)

    await store.logout()

    expect(authApi.logout).toHaveBeenCalledTimes(1)
    expect(store.isAuthenticated).toBe(false)
    expect(store.user).toBeNull()
    expect(window.localStorage.getItem('sg4:access_token')).toBeNull()
  })

  it('无令牌时 hydrate 不请求接口', async () => {
    const store = useAuthStore()
    await store.hydrate()

    expect(authApi.getMe).not.toHaveBeenCalled()
    expect(store.hydrated).toBe(true)
    expect(store.isAuthenticated).toBe(false)
  })

  it('有令牌时 hydrate 恢复会话', async () => {
    window.localStorage.setItem('sg4:access_token', 'access-token-1')
    vi.mocked(authApi.getMe).mockResolvedValue(mockUser)

    const store = useAuthStore()
    await store.hydrate()

    expect(store.user?.username).toBe('admin')
    expect(store.isAuthenticated).toBe(true)
    expect(store.hydrated).toBe(true)
  })

  it('刷新令牌会轮换 refresh_token', async () => {
    vi.mocked(authApi.refresh).mockResolvedValue({
      ...mockTokens,
      access_token: 'access-token-2',
      refresh_token: 'refresh-token-2',
    })

    const store = useAuthStore()
    store.applyTokens(mockTokens)
    const token = await store.refreshSession()

    expect(token).toBe('access-token-2')
    expect(window.localStorage.getItem('sg4:refresh_token')).toBe('refresh-token-2')
  })

  it('密码修改调用接口且不改动本地状态', async () => {
    vi.mocked(authApi.changePassword).mockResolvedValue({ message: 'ok' })
    const store = useAuthStore()
    store.applyTokens(mockTokens)

    await store.changePassword('old-pass1', 'new-pass1')

    expect(authApi.changePassword).toHaveBeenCalledWith({
      old_password: 'old-pass1',
      new_password: 'new-pass1',
    })
    expect(store.isAuthenticated).toBe(true)
  })
})
