/** 认证相关类型 (对齐 apps/api/app/schemas/auth.py) */

/** 令牌对 (登录 / 刷新返回; refresh_token 为一次性, 单次使用后轮换) */
export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  /** access_token 有效期 (秒) */
  expires_in: number
}

/** 登录请求体 (username 支持用户名或邮箱) */
export interface LoginPayload {
  username: string
  password: string
}

/** 注册请求体 */
export interface RegisterPayload {
  username: string
  email: string
  password: string
  full_name?: string
}

/** 刷新令牌请求体 */
export interface RefreshPayload {
  refresh_token: string
}

/** 修改密码请求体 */
export interface ChangePasswordPayload {
  old_password: string
  new_password: string
}

/** 当前登录用户资料 (GET /auth/me) */
export interface CurrentUser {
  id: number
  username: string
  email: string
  full_name: string | null
  avatar: string | null
  phone: string | null
  is_active: boolean
  is_superuser: boolean
  last_login_at: string | null
  roles: string[]
  permissions: string[]
}

/** 个人资料更新 (PATCH /auth/me) */
export interface ProfileUpdatePayload {
  email?: string
  full_name?: string
  phone?: string
}
