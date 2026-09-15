/** 用户管理接口 (需要 users:read / users:write 权限) */

import { del, get, patch, post, put } from '@/utils/request'
import type { IdResponse, Paginated } from '@/types/common'
import type {
  ResetPasswordResponse,
  RoleAssignPayload,
  UserCreatePayload,
  UserListItem,
  UserListQuery,
  UserStats,
  UserUpdatePayload,
} from '@/types/user'
import type { Role } from '@/types/role'

/** 用户分页列表 */
export function listUsers(query: UserListQuery = {}): Promise<Paginated<UserListItem>> {
  return get<Paginated<UserListItem>>('/users', { ...query })
}

/** 用户统计 */
export function getUserStats(): Promise<UserStats> {
  return get<UserStats>('/users/stats')
}

/** 可选角色 (创建/编辑用户时的下拉数据源) */
export function getRoleOptions(): Promise<Role[]> {
  return get<Role[]>('/users/roles/options')
}

/** 创建用户 */
export function createUser(payload: UserCreatePayload): Promise<UserListItem> {
  return post<UserListItem>('/users', payload)
}

/** 更新用户 */
export function updateUser(id: number, payload: UserUpdatePayload): Promise<UserListItem> {
  return patch<UserListItem>(`/users/${id}`, payload)
}

/** 分配角色 */
export function assignRoles(id: number, payload: RoleAssignPayload): Promise<UserListItem> {
  return put<UserListItem>(`/users/${id}/roles`, payload)
}

/** 启用 / 禁用 */
export function toggleUserActive(id: number): Promise<UserListItem> {
  return post<UserListItem>(`/users/${id}/toggle-active`)
}

/** 重置密码 (返回随机新密码, 仅本次可见) */
export function resetUserPassword(id: number): Promise<ResetPasswordResponse> {
  return post<ResetPasswordResponse>(`/users/${id}/reset-password`)
}

/** 删除用户 */
export function deleteUser(id: number): Promise<IdResponse> {
  return del<IdResponse>(`/users/${id}`)
}
