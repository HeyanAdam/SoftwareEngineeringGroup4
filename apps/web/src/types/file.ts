/** 文件管理类型 (对齐 apps/api/app/schemas/file.py) */

/** 文件记录 (GET /files) */
export interface FileItem {
  id: number
  object_name: string
  bucket: string
  original_name: string
  content_type: string
  size: number
  category: string
  status: string
  owner_id: number | null
  created_at: string
  updated_at: string
}

/** 文件统计 (GET /files/stats) */
export interface FileStats {
  files: number
  bytes: number
}

/** 文件列表查询参数 */
export interface FileListQuery {
  page?: number
  page_size?: number
  category?: string
  keyword?: string
  only_mine?: boolean
}

/** 直传 URL 申请 (POST /files/presign-upload) */
export interface PresignUploadPayload {
  filename: string
  content_type: string
  category: string
  size?: number
}

/** 直传 URL 响应 */
export interface PresignUploadResponse {
  upload_url: string
  object_name: string
  bucket: string
  expires_in: number
}

/** 直传完成登记 (POST /files/complete) */
export interface CompleteUploadPayload {
  object_name: string
  original_name: string
  content_type: string
  size: number
  category: string
}

/** 下载地址响应 (GET /files/{id}/download) */
export interface DownloadUrlResponse {
  url: string
  expires_in: number
  original_name: string
}

/** 文件分类选项 (后端为自由字符串, 前端给出常用枚举) */
export interface FileCategoryOption {
  value: string
  label: string
}
