/** 仪表盘类型 (对齐 apps/api/app/schemas/common.py DashboardOverview) */

/** 指标卡 */
export interface DashboardStat {
  key: string
  label: string
  value: number
  unit: string | null
  delta: number | null
}

/** 单点数据 */
export interface DashboardPoint {
  label: string
  value: number
}

/** 总览响应 (GET /dashboard/overview) */
export interface DashboardOverview {
  stats: DashboardStat[]
  trend: DashboardPoint[]
  categories: DashboardPoint[]
  role_distribution: DashboardPoint[]
  generated_at: string
  extra: Record<string, unknown>
}

/** 总览查询参数 */
export interface DashboardQuery {
  days?: number
  refresh?: boolean
}
