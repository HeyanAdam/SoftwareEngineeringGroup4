/** 用户模块接口，对应后端 /api/user/* */
import { request } from '@/utils/request'
import type {
  LoginPayload,
  LoginResponse,
  RegisterPayload,
  RegisterResponse,
  UserProfile,
  UserUpdatePayload,
} from '@/types/user'

/** 注册新用户 */
export function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request.post<RegisterResponse>('/user/register', payload)
}

/** 账号密码登录，返回 access_token 与用户信息 */
export function login(payload: LoginPayload): Promise<LoginResponse> {
  return request.post<LoginResponse>('/user/login', payload)
}

/** 获取当前登录用户资料 */
export function getProfile(): Promise<UserProfile> {
  return request.get<UserProfile>('/user/me')
}

/** 更新当前用户资料，返回更新后的完整资料 */
export function updateProfile(payload: UserUpdatePayload): Promise<UserProfile> {
  return request.put<UserProfile>('/user/me', payload)
}
