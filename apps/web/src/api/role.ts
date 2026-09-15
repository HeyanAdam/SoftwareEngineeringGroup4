/** 角色与权限接口 */

import { del, get, patch, post } from '@/utils/request'
import type { IdResponse, PermissionOut } from '@/types/common'
import type { Role, RoleCreatePayload, RoleUpdatePayload } from '@/types/role'

/** 角色列表 */
export function listRoles(): Promise<Role[]> {
  return get<Role[]>('/roles')
}

/** 权限点全量列表 (按 module 分组渲染权限树) */
export function listPermissions(): Promise<PermissionOut[]> {
  return get<PermissionOut[]>('/roles/permissions')
}

/** 创建角色 */
export function createRole(payload: RoleCreatePayload): Promise<Role> {
  return post<Role>('/roles', payload)
}

/** 更新角色 (code 不可修改) */
export function updateRole(id: number, payload: RoleUpdatePayload): Promise<Role> {
  return patch<Role>(`/roles/${id}`, payload)
}

/** 删除角色 (内置角色 / 仍被引用的角色会被后端拒绝) */
export function deleteRole(id: number): Promise<IdResponse> {
  return del<IdResponse>(`/roles/${id}`)
}
