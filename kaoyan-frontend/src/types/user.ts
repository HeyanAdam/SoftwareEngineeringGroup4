/** 用户模块类型定义，对应后端 /api/user/* */

/** 登录响应里的用户信息（POST /user/login） */
export interface UserInfo {
  id: number
  username: string
  email: string
  nickname: string
}

/** 当前用户完整资料（GET /user/me） */
export interface UserProfile {
  id: number
  username: string
  email: string
  nickname: string
  target_school: string | null
  target_major: string | null
  exam_year: number | null
  created_at: string
}

/** POST /user/login 响应 */
export interface LoginResponse {
  access_token: string
  token_type: string
  user: UserInfo
}

/** POST /user/login 请求体 */
export interface LoginPayload {
  username: string
  password: string
}

/** POST /user/register 请求体 */
export interface RegisterPayload {
  username: string
  email: string
  password: string
  nickname?: string
}

/** POST /user/register 响应 */
export interface RegisterResponse {
  id: number
  username: string
  email: string
  nickname: string
}

/** PUT /user/me 请求体（只提交要修改的字段） */
export interface UserUpdatePayload {
  nickname?: string
  target_school?: string
  target_major?: string
  exam_year?: number
}

/** 登录表单模型 */
export interface LoginForm {
  username: string
  password: string
}

/** 注册表单模型 */
export interface RegisterForm {
  username: string
  email: string
  password: string
  confirmPassword: string
}

/** 个人中心表单模型：与 PUT /user/me 字段保持一致 */
export type ProfileForm = UserUpdatePayload
