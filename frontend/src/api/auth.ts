/** 用户模块接口，对应后端 /api/user/* */

import { request } from '@/utils/request'
import type {
  CaptchaInfo,
  ChangePasswordPayload,
  EmailLoginPayload,
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  RegisterResponse,
  ResetPasswordPayload,
  SendEmailCodePayload,
  SendEmailCodeResponse,
  UserInfo,
  UserProfile,
  UserUpdatePayload,
} from '@/types/user'

/** 用户名 + 密码登录 */
export function login(payload: LoginPayload): Promise<LoginResponse> {
  return request.post<LoginResponse>('/user/login', payload)
}

/** 获取图形验证码（密码登录连续失败后强制要求） */
export function getCaptcha(): Promise<CaptchaInfo> {
  return request.get<CaptchaInfo>('/user/captcha')
}

/** 邮箱验证码登录 */
export function loginByEmail(payload: EmailLoginPayload): Promise<LoginResponse> {
  return request.post<LoginResponse>('/user/login/email', payload)
}

/** 发送邮箱验证码（登录 / 找回密码） */
export function sendEmailCode(payload: SendEmailCodePayload): Promise<SendEmailCodeResponse> {
  return request.post<SendEmailCodeResponse>('/user/email-code', payload)
}

/** 注册 */
export function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request.post<RegisterResponse>('/user/register', payload)
}

/** 当前登录用户资料 */
export function getProfile(): Promise<UserProfile> {
  return request.get<UserProfile>('/user/me')
}

/** 修改资料 */
export function updateProfile(payload: UserUpdatePayload): Promise<UserProfile> {
  return request.put<UserProfile>('/user/me', payload)
}

/** 当前用户的角色与权限 */
export function getPermissions(): Promise<{ roles: string[]; permissions: string[] }> {
  return request.get<{ roles: string[]; permissions: string[] }>('/user/permissions')
}

/** 退出登录：后端会把当前令牌加入吊销名单 */
export function logout(): Promise<{ message: string }> {
  return request.post<{ message: string }>('/user/logout')
}

/** 已登录状态下修改密码（改完需要重新登录） */
export function changePassword(payload: ChangePasswordPayload): Promise<{ message: string }> {
  return request.post<{ message: string }>('/user/password/change', payload)
}

/** 用邮箱验证码重置密码（未登录可用） */
export function resetPassword(payload: ResetPasswordPayload): Promise<{ message: string }> {
  return request.post<{ message: string }>('/user/password/reset', payload)
}

/** 登录响应里的用户信息（保留此别名，兼容旧代码引用） */
export type { UserInfo }
