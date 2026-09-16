/**
 * 通用接口类型定义。
 *
 * 后端约定（与后端 agent 对齐）：
 * - 成功：HTTP 2xx，响应体就是数据本身，没有 { code, data } 外壳
 * - 失败：HTTP 4xx/5xx，响应体形如 { code, message, data }
 */

/** 后端失败响应体 */
export interface ApiErrorBody {
  code: number
  message: string
  data: null
}

/** 删除类接口的统一响应 */
export interface DeleteResult {
  message: string
}
