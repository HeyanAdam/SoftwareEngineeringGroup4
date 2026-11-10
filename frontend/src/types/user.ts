/** 用户模块类型定义，对应后端 /api/user/* */

/**
 * 登录响应里的用户信息（POST /user/login）
 * 本次改造新增：后端会在登录响应里带上 roles / permissions，供前端渲染菜单。
 * 这两个字段是可选的原因：老版本接口返回时没有它们，兼容处理不会报错。
 */
export interface UserInfo {
  id: number
  username: string
  email: string
  nickname: string
  display_name?: string
  roles?: string[]
  permissions?: string[]
}

/** 当前用户完整资料（GET /user/me） */
export interface UserProfile {
  id: number
  username: string
  email: string
  nickname: string
  display_name?: string
  /** 以下五项与后端 user_account 表一一对应（《权限表》ER 图口径） */
  undergraduate_major: string | null
  major: string | null
  target_area: string | null
  prep_stage: string | null
  target_score: number | null
  created_at: string
  roles: string[]
  permissions: string[]
}

/** POST /user/login 响应 */
export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: UserInfo
  roles: string[]
  permissions: string[]
}

/** POST /user/login 请求体 */
export interface LoginPayload {
  username: string
  password: string
  /** 连续失败后必填：图形验证码 ID 与答案 */
  captcha_id?: string
  captcha_code?: string
}

/** GET /user/captcha 响应（密码登录防机器人） */
export interface CaptchaInfo {
  captcha_id: string
  svg: string
  expires_in: number
}

/** POST /user/login/email 请求体（邮箱验证码登录） */
export interface EmailLoginPayload {
  email: string
  code: string
}

/** POST /user/email-code 请求体 */
export interface SendEmailCodePayload {
  email: string
  /** 用途：登录 / 找回密码 */
  purpose: 'login' | 'reset'
}

/** POST /user/email-code 响应 */
export interface SendEmailCodeResponse {
  /** smtp = 真实发信；console = 开发期兜底回显 */
  channel: 'smtp' | 'console'
  expires_in: number
  resend_after: number
  /** 仅兜底通道返回值，生产环境恒为 null */
  dev_code: string | null
  email: string
}

/** POST /user/password/reset 请求体 */
export interface ResetPasswordPayload {
  email: string
  code: string
  new_password: string
}

/** POST /user/password/change 请求体 */
export interface ChangePasswordPayload {
  old_password: string
  new_password: string
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
  undergraduate_major?: string
  major?: string
  target_area?: string
  prep_stage?: string
  target_score?: number
}

/** 登录表单模型 */
export interface LoginForm {
  username: string
  password: string
}

/** 邮箱验证码登录表单模型 */
export interface EmailLoginForm {
  email: string
  code: string
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
