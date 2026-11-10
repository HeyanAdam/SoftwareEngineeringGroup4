/** 授权(后台管理)接口，对应后端 /api/admin/*（均需对应权限，服务端强校验） */

import { request } from '@/utils/request'
import type {
  AdminUserItem,
  AdminUserPage,
  AuditLogPage,
  PermissionGroup,
  RoleBrief,
  RoleItem,
  RolePayload,
} from '@/types/rbac'

/** 角色列表 */
export function listRoles(): Promise<RoleItem[]> {
  return request.get<RoleItem[]>('/admin/roles')
}

/** 新增角色 */
export function createRole(payload: RolePayload): Promise<RoleItem> {
  return request.post<RoleItem>('/admin/roles', payload)
}

/** 修改角色 */
export function updateRole(roleId: number, payload: RolePayload): Promise<RoleItem> {
  return request.put<RoleItem>(`/admin/roles/${roleId}`, payload)
}

/** 删除角色 */
export function deleteRole(roleId: number): Promise<{ message: string }> {
  return request.delete<{ message: string }>(`/admin/roles/${roleId}`)
}

/** 权限清单（按模块分组） */
export function listPermissions(): Promise<PermissionGroup[]> {
  return request.get<PermissionGroup[]>('/admin/permissions')
}

/** 某角色已授权的权限编号 */
export function getRolePermissions(roleId: number): Promise<number[]> {
  return request.get<number[]>(`/admin/roles/${roleId}/permissions`)
}

/** 保存角色权限勾选结果（整体覆盖） */
export function updateRolePermissions(roleId: number, permIds: number[]): Promise<number[]> {
  return request.put<number[]>(`/admin/roles/${roleId}/permissions`, { perm_ids: permIds })
}

/** 用户列表 */
export function listUsers(params: {
  keyword?: string
  page?: number
  size?: number
}): Promise<AdminUserPage> {
  return request.get<AdminUserPage>('/admin/users', { params })
}

/** 给用户分配角色 */
export function updateUserRoles(userId: number, roleIds: number[]): Promise<RoleBrief[]> {
  return request.put<RoleBrief[]>(`/admin/users/${userId}/roles`, { role_ids: roleIds })
}

/** 启用 / 禁用账号 */
export function updateUserStatus(userId: number, accountStatus: 0 | 1): Promise<AdminUserItem> {
  return request.patch<AdminUserItem>(`/admin/users/${userId}/status`, {
    account_status: accountStatus,
  })
}

/** 审计日志（按动作精确筛选 + 分页） */
export function listAuditLogs(params: {
  action?: string
  page?: number
  size?: number
}): Promise<AuditLogPage> {
  return request.get<AuditLogPage>('/admin/audit-logs', { params })
}
