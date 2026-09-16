/** 学习规划模块接口，对应后端 /api/plan/*（均需登录） */
import { request } from '@/utils/request'
import type { DeleteResult } from '@/types/api'
import type {
  CreatePlanPayload,
  PlanDetail,
  PlanStats,
  PlanTask,
  StudyPlan,
  UpdateTaskPayload,
} from '@/types/plan'

/** 计划列表 */
export function listPlans(): Promise<StudyPlan[]> {
  return request.get<StudyPlan[]>('/plan/plans')
}

/** 新建计划 */
export function createPlan(payload: CreatePlanPayload): Promise<StudyPlan> {
  return request.post<StudyPlan>('/plan/plans', payload)
}

/** 计划详情（含任务列表） */
export function getPlan(planId: number): Promise<PlanDetail> {
  return request.get<PlanDetail>(`/plan/plans/${planId}`)
}

/** 删除计划 */
export function deletePlan(planId: number): Promise<DeleteResult> {
  return request.delete<DeleteResult>(`/plan/plans/${planId}`)
}

/** 更新任务状态 / 备注，返回更新后的任务 */
export function updateTask(taskId: number, payload: UpdateTaskPayload): Promise<PlanTask> {
  return request.patch<PlanTask>(`/plan/tasks/${taskId}`, payload)
}

/** 学习统计概览 */
export function getStats(): Promise<PlanStats> {
  return request.get<PlanStats>('/plan/stats')
}
