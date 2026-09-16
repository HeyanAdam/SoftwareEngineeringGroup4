"""学习规划模块接口: 计划、任务与进度统计。"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.chat import SimpleMessage
from app.schemas.plan import (
    PlanCreateRequest,
    PlanDetailOut,
    PlanOut,
    PlanStatsOut,
    PlanUpdateRequest,
    TaskOut,
    TaskUpdateRequest,
)
from app.services.plan_service import StudyPlanService, to_plan_out

router = APIRouter(prefix="/api/plan", tags=["学习规划模块"])


@router.get("/plans", response_model=list[PlanOut], summary="我的学习计划")
def list_plans(user: CurrentUser, db: DbSession) -> list[PlanOut]:
    plans = StudyPlanService(db).list_plans(user.id)
    return [PlanOut(**to_plan_out(plan)) for plan in plans]


@router.post(
    "/plans",
    response_model=PlanOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建学习计划(自动拆解每日任务)",
)
def create_plan(
    payload: PlanCreateRequest, user: CurrentUser, db: DbSession
) -> PlanOut:
    plan = StudyPlanService(db).create_plan(
        user.id,
        title=payload.title,
        subject=payload.subject,
        start_date=payload.start_date,
        end_date=payload.end_date,
        daily_minutes=payload.daily_minutes,
        note=payload.note,
    )
    return PlanOut(**to_plan_out(plan))


@router.get("/plans/{plan_id}", response_model=PlanDetailOut, summary="计划详情(含任务)")
def get_plan(plan_id: int, user: CurrentUser, db: DbSession) -> PlanDetailOut:
    plan = StudyPlanService(db).get_plan(plan_id, user.id)
    data = to_plan_out(plan)
    return PlanDetailOut(
        **data,
        note=plan.note,
        tasks=[TaskOut.model_validate(task) for task in plan.tasks],
    )


@router.patch("/plans/{plan_id}", response_model=PlanOut, summary="修改计划")
def update_plan(
    plan_id: int, payload: PlanUpdateRequest, user: CurrentUser, db: DbSession
) -> PlanOut:
    plan = StudyPlanService(db).update_plan(
        plan_id,
        user.id,
        title=payload.title,
        subject=payload.subject,
        daily_minutes=payload.daily_minutes,
        status=payload.status,
        note=payload.note,
    )
    return PlanOut(**to_plan_out(plan))


@router.delete("/plans/{plan_id}", response_model=SimpleMessage, summary="删除计划")
def delete_plan(plan_id: int, user: CurrentUser, db: DbSession) -> SimpleMessage:
    StudyPlanService(db).delete_plan(plan_id, user.id)
    return SimpleMessage(message="计划已删除")


@router.patch("/tasks/{task_id}", response_model=TaskOut, summary="更新任务状态")
def update_task(
    task_id: int, payload: TaskUpdateRequest, user: CurrentUser, db: DbSession
) -> TaskOut:
    task = StudyPlanService(db).update_task(
        task_id, user.id, status=payload.status, note=payload.note
    )
    return TaskOut.model_validate(task)


@router.get("/stats", response_model=PlanStatsOut, summary="学习进度统计")
def stats(user: CurrentUser, db: DbSession) -> PlanStatsOut:
    return PlanStatsOut(**StudyPlanService(db).stats(user.id))


@router.get("/ping", summary="模块自检")
def ping() -> dict[str, str]:
    return {"module": "study_plan", "message": "学习规划模块运行正常"}
