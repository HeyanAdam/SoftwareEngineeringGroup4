/** 仪表盘接口 */

import { get, post } from '@/utils/request'
import type { DashboardOverview, DashboardQuery } from '@/types/dashboard'
import type { MsgResponse } from '@/types/common'

/** 总览数据 (stats / trend / categories / role_distribution) */
export function getOverview(query: DashboardQuery = {}): Promise<DashboardOverview> {
  return get<DashboardOverview>('/dashboard/overview', { ...query })
}

/** 清除仪表盘缓存 */
export function refreshDashboardCache(): Promise<MsgResponse> {
  return post<MsgResponse>('/dashboard/cache/refresh')
}
