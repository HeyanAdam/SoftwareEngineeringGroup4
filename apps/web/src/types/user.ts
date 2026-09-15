/** 用户管理类型 (对齐 apps/api/app/schemas/auth.py + user_helpers.py) */

/** 用户列表项 (GET /users) */
export interface UserListItem {
  id: number
  username: string
  email: string
  full_name: string | null
  avatar: string | null
  is_active: boolean
  is_superuser: boolean
  last_login_at: string | null
  created_at: string
  roles: string[]
}

/** 用户统计 (GET /users/stats) */
export interface UserStats {
  total: number
  active: number
  inactive: number
  superusers: number
  [key: string]: number
}

/** 用户列表查询参数 */
export interface UserListQuery {
  page?: number
  page_size?: number
  keyword?: string
  is_active?: boolean
  role?: string
  sort_by?: string
}

/** 创建用户请求体 (POST /users) */
export interface UserCreatePayload {
  username: string
  email: string
  password: string
  full_name?: string
  is_active?: boolean
  roles?: string[]
}

/** 更新用户请求体 (PATCH /users/{id}) */
export interface UserUpdatePayload {
  email?: string
  full_name?: string
  phone?: string
  is_active?: boolean
  remark?: string
  roles?: string[]
}

/** 分配角色请求体 (PUT /users/{id}/roles) */
export interface RoleAssignPayload {
  role_codes: string[]
}

/** 重置密码响应 (POST /users/{id}/reset-password) */
export interface ResetPasswordResponse {
  password: string
}
