/** 文件管理接口 (MinIO, 支持服务端中转与前端直传两种方式) */

import axios from 'axios'

import { del, get, post, upload } from '@/utils/request'
import type { IdResponse, Paginated } from '@/types/common'
import type {
  CompleteUploadPayload,
  DownloadUrlResponse,
  FileItem,
  FileListQuery,
  FileStats,
  PresignUploadPayload,
  PresignUploadResponse,
} from '@/types/file'

/** 文件分页列表 */
export function listFiles(query: FileListQuery = {}): Promise<Paginated<FileItem>> {
  return get<Paginated<FileItem>>('/files', { ...query })
}

/** 文件统计 (数量 + 总字节数) */
export function getFileStats(): Promise<FileStats> {
  return get<FileStats>('/files/stats')
}

/** 服务端中转上传 (multipart, 字段名 file + category) */
export function uploadFile(
  file: File,
  category = 'attachment',
  onProgress?: (percent: number) => void,
): Promise<FileItem> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('category', category)
  return upload<FileItem>('/files/upload', formData, undefined, onProgress)
}

/** 申请直传 URL */
export function presignUpload(payload: PresignUploadPayload): Promise<PresignUploadResponse> {
  return post<PresignUploadResponse>('/files/presign-upload', payload)
}

/**
 * 直传完成后登记文件记录。
 * 注意: PUT 到 MinIO 的预签名 URL 时不能携带 Authorization 头。
 */
export function completeUpload(payload: CompleteUploadPayload): Promise<FileItem> {
  return post<FileItem>('/files/complete', payload)
}

/**
 * 前端直传完整流程: 申请 URL -> PUT 原始 body -> 登记。
 * 断点/取消能力暂不需要, 保留 AbortSignal 便于页面卸载时中断。
 */
export async function uploadFileByPresign(
  file: File,
  category = 'attachment',
  onProgress?: (percent: number) => void,
): Promise<FileItem> {
  const presigned = await presignUpload({
    filename: file.name,
    content_type: file.type || 'application/octet-stream',
    category,
    size: file.size,
  })

  await axios.put(presigned.upload_url, file, {
    timeout: 120_000,
    headers: { 'Content-Type': file.type || 'application/octet-stream' },
    transformRequest: [(data: unknown) => data],
    onUploadProgress: (event) => {
      if (!onProgress) return
      const total = event.total ?? file.size
      if (total > 0) onProgress(Math.round((event.loaded / total) * 100))
    },
  })

  return completeUpload({
    object_name: presigned.object_name,
    original_name: file.name,
    content_type: file.type || 'application/octet-stream',
    size: file.size,
    category,
  })
}

/** 获取预签名下载地址 */
export function getDownloadUrl(id: number): Promise<DownloadUrlResponse> {
  return get<DownloadUrlResponse>(`/files/${id}/download`)
}

/** 删除文件 */
export function deleteFile(id: number): Promise<IdResponse> {
  return del<IdResponse>(`/files/${id}`)
}
