/** 认证接口 (全部路径相对 VITE_API_BASE_URL) */

import { get, patch, post } from '@/utils/request'
import type {
  ChangePasswordPayload,
  CurrentUser,
  LoginPayload,
  ProfileUpdatePayload,
  RefreshPayload,
  RegisterPayload,
  TokenPair,
} from '@/types/auth'
import type { MsgResponse } from '@/types/common'

/** 登录 (用户名或邮箱) */
export function login(payload: LoginPayload): Promise<TokenPair> {
  return post<TokenPair>('/auth/login', payload, { silent: true })
}

/** 注册 (返回创建好的用户资料) */
export function register(payload: RegisterPayload): Promise<CurrentUser> {
  return post<CurrentUser>('/auth/register', payload)
}

/** 刷新令牌 (refresh_token 单次使用并轮换) */
export function refresh(payload: RefreshPayload): Promise<TokenPair> {
  return post<TokenPair>('/auth/refresh', payload, { silent: true })
}

/** 退出登录 (令牌版本 +1, 旧令牌立即失效) */
export function logout(): Promise<MsgResponse> {
  return post<MsgResponse>('/auth/logout', undefined, { silent: true })
}

/** 当前登录用户资料 (含 roles / permissions) */
export function getMe(): Promise<CurrentUser> {
  return get<CurrentUser>('/auth/me')
}

/** 更新个人资料 */
export function updateMe(payload: ProfileUpdatePayload): Promise<CurrentUser> {
  return patch<CurrentUser>('/auth/me', payload)
}

/** 修改密码 (成功后需要重新登录) */
export function changePassword(payload: ChangePasswordPayload): Promise<MsgResponse> {
  return post<MsgResponse>('/auth/change-password', payload)
}

/** 当前用户权限码列表 */
export function getMyPermissions(): Promise<string[]> {
  return get<string[]>('/auth/permissions')
}
