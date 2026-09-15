/** 角色与权限类型 (对齐 apps/api/app/schemas/role.py) */

import type { PermissionOut } from './common'

/** 角色 (GET /roles, GET /users/roles/options) */
export interface Role {
  id: number
  code: string
  name: string
  description: string | null
  is_builtin: boolean
  permissions: string[]
  created_at: string
  updated_at: string
}

/** 创建角色请求体 */
export interface RoleCreatePayload {
  code: string
  name: string
  description?: string
  permissions?: string[]
}

/** 更新角色请求体 (code 不可改) */
export interface RoleUpdatePayload {
  name?: string
  description?: string
  permissions?: string[]
}

/** 权限点按模块分组的树节点 (用于 el-tree 展示) */
export interface PermissionModuleGroup {
  module: string
  label: string
  children: PermissionOut[]
}
