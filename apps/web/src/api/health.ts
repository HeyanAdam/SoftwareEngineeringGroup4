/** 健康检查接口 (全部位于 /api/v1 之下) */

import { get } from '@/utils/request'

/** 存活探针响应 */
export interface HealthLive {
  status: string
  app: string
  version: string
  env: string
  instance: string
  uptime_seconds: number
}

/** 就绪探针响应 */
export interface HealthReady {
  status: string
  checks: Record<string, string | number>
}

/** 运行时信息 */
export interface HealthInfo {
  app: string
  version: string
  git_sha: string
  env: string
  debug: boolean
  python: string
  platform: string
  instance: string
  uptime_seconds: number
  ws_connections: number
  ws_rooms: number
}

/** 存活探针 */
export function live(): Promise<HealthLive> {
  return get<HealthLive>('/health/live', undefined, { silent: true })
}

/** 就绪探针 (依赖检查) */
export function ready(): Promise<HealthReady> {
  return get<HealthReady>('/health/ready', undefined, { silent: true })
}

/** 运行时信息 */
export function info(): Promise<HealthInfo> {
  return get<HealthInfo>('/health/info', undefined, { silent: true })
}
