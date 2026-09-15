/**
 * 通用接口类型: 分页 / 错误信封 / ID 响应。
 * 后端约定: 成功响应直接返回资源本体, 失败统一为 { code, message, data? }。
 */

/** 分页元信息 */
export interface PageMeta {
  page: number
  page_size: number
  total: number
  pages: number
}

/** 分页响应体 */
export interface Paginated<T> {
  items: T[]
  meta: PageMeta
}

/** 统一错误信封 (HTTP status + JSON) */
export interface ApiErrorBody {
  code: number
  message: string
  data?: unknown
}

/** 归一化后的接口错误, 供业务层 catch 使用 */
export interface NormalizedApiError extends ApiErrorBody {
  status: number
}

/** 通用简单消息响应 */
export interface MsgResponse {
  message: string
}

/** 通用 ID 响应 */
export interface IdResponse {
  id: number
}

/** 权限点 (GET /roles/permissions) */
export interface PermissionOut {
  id: number
  code: string
  name: string
  module: string
  description: string | null
}
