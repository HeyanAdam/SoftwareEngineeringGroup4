/** 授权(后台管理)模块类型定义，对应后端 /api/admin/* */

/** 角色：user_count / permission_ids / built_in 由后端一并返回，管理页直接用 */
export interface RoleItem {
  role_id: number
  role_name: string
  role_desc: string | null
  user_count: number
  permission_ids: number[]
  built_in: boolean
}

/** 单条权限 */
export interface PermissionItem {
  perm_id: number
  perm_key: string
  perm_name: string
  module_name: string
}

/** 按模块分组的权限清单（后台勾选用） */
export interface PermissionGroup {
  module_name: string
  permissions: PermissionItem[]
}

/** 账号状态：0 禁用 / 1 启用 */
export type AccountStatus = 0 | 1

export interface RoleBrief {
  role_id: number
  role_name: string
}

export interface AdminUserItem {
  user_id: number
  login_name: string
  email: string
  account_status: AccountStatus
  create_time: string
  roles: RoleBrief[]
}

export interface AdminUserPage {
  total: number
  items: AdminUserItem[]
}

export interface AuditLogItem {
  id: number
  user_id: number | null
  login_name: string | null
  action: string
  target_type: string | null
  target_id: string | null
  detail: Record<string, unknown> | null
  ip: string | null
  success: boolean
  create_time: string
}

export interface AuditLogPage {
  total: number
  items: AuditLogItem[]
}

export interface RolePayload {
  role_name: string
  role_desc?: string | null
}
