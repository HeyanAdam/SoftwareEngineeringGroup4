/** 学习规划模块类型定义，对应后端 /api/plan/* */

/** 任务状态 */
export type TaskStatus = 'pending' | 'done'

/** 计划状态 */
export type PlanStatus = 'pending' | 'active' | 'completed'

/** 计划列表元素（GET /plan/plans） */
export interface StudyPlan {
  id: number
  title: string
  subject: string
  start_date: string
  end_date: string
  daily_minutes: number
  status: string
  progress: number
  task_total: number
  task_done: number
  created_at: string
}

/** 计划下的任务 */
export interface PlanTask {
  id: number
  plan_id: number
  title: string
  day_index: number
  scheduled_date: string
  status: TaskStatus
  note: string | null
}

/** 计划详情（GET /plan/plans/{id}）= 计划字段 + tasks */
export interface PlanDetail extends StudyPlan {
  tasks: PlanTask[]
}

/** POST /plan/plans 请求体 */
export interface CreatePlanPayload {
  title: string
  subject: string
  start_date: string
  end_date: string
  daily_minutes: number
  note?: string
}

/** PATCH /plan/tasks/{id} 请求体 */
export interface UpdateTaskPayload {
  status?: TaskStatus
  note?: string
}

/** GET /plan/stats 响应 */
export interface PlanStats {
  plan_total: number
  plan_active: number
  task_total: number
  task_done: number
  completion_rate: number
}

/** 新建计划表单模型（日期用 YYYY-MM-DD 字符串，与后端一致） */
export type PlanForm = CreatePlanPayload
