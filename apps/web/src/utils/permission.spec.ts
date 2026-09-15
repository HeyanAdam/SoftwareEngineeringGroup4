/** 权限判定工具单元测试 */

import { describe, expect, it } from 'vitest'

import {
  checkAccess,
  hasAnyPermission,
  hasPermission,
  hasRole,
  moduleLabel,
  SUPER_PERMISSION,
} from '@/utils/permission'

describe('hasPermission', () => {
  const perms = ['users:read', 'files:upload']

  it('未声明权限要求时直接通过', () => {
    expect(hasPermission([], undefined)).toBe(true)
    expect(hasPermission([], null)).toBe(true)
    expect(hasPermission([], [])).toBe(true)
  })

  it('精确匹配', () => {
    expect(hasPermission(perms, 'users:read')).toBe(true)
    expect(hasPermission(perms, 'users:write')).toBe(false)
  })

  it('数组要求为"全部满足"', () => {
    expect(hasPermission(perms, ['users:read', 'files:upload'])).toBe(true)
    expect(hasPermission(perms, ['users:read', 'users:write'])).toBe(false)
  })

  it('支持 module:* 通配', () => {
    expect(hasPermission(['users:*'], 'users:delete')).toBe(true)
    expect(hasPermission(['users:*'], 'roles:read')).toBe(false)
  })

  it('支持全局通配与超级管理员', () => {
    expect(hasPermission([SUPER_PERMISSION], 'anything:at-all')).toBe(true)
    expect(hasPermission([], 'users:read', true)).toBe(true)
    expect(hasPermission([], 'users:read', false)).toBe(false)
  })

  it('单值入参与数组入参等价', () => {
    expect(hasPermission(perms, 'users:read')).toBe(hasPermission(perms, ['users:read']))
  })
})

describe('hasAnyPermission', () => {
  const perms = ['files:read']

  it('满足任意一项即可', () => {
    expect(hasAnyPermission(perms, ['users:read', 'files:read'])).toBe(true)
    expect(hasAnyPermission(perms, ['users:read', 'roles:read'])).toBe(false)
    expect(hasAnyPermission(perms, [])).toBe(true)
  })
})

describe('hasRole', () => {
  const roles = ['admin', 'editor']

  it('角色判定', () => {
    expect(hasRole(roles, 'admin')).toBe(true)
    expect(hasRole(roles, ['viewer', 'editor'])).toBe(true)
    expect(hasRole(roles, 'viewer')).toBe(false)
    expect(hasRole(roles, undefined)).toBe(true)
    expect(hasRole([], 'admin', true)).toBe(true)
  })
})

describe('checkAccess', () => {
  const context = { permissions: ['users:read', 'files:upload'], roles: ['editor'] }

  it('权限与角色同时满足才通过', () => {
    expect(checkAccess(context, { permissions: ['users:read'], roles: ['editor'] })).toBe(true)
    expect(checkAccess(context, { permissions: ['users:write'], roles: ['editor'] })).toBe(false)
    expect(checkAccess(context, { permissions: ['users:read'], roles: ['admin'] })).toBe(false)
  })

  it('未声明的维度不限制', () => {
    expect(checkAccess(context, {})).toBe(true)
    expect(checkAccess(context, undefined)).toBe(true)
    expect(checkAccess(context, { permissions: ['users:read'] })).toBe(true)
  })

  it('超级管理员直通', () => {
    expect(
      checkAccess({ ...context, isSuperuser: true }, { permissions: ['roles:write'] }),
    ).toBe(true)
  })
})

describe('moduleLabel', () => {
  it('已知模块返回中文名, 未知模块回退原名', () => {
    expect(moduleLabel('users')).toBe('用户管理')
    expect(moduleLabel('unknown')).toBe('unknown')
  })
})
