"""学习规划模块业务逻辑。

创建计划时会自动把时间跨度拆解成每日任务, 让学生「打开就有事可做」。
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.plan import (
    PLAN_STATUS_ACTIVE,
    PLAN_STATUS_DONE,
    TASK_STATUS_DONE,
    TASK_STATUS_PENDING,
    StudyPlan,
    StudyPlanTask,
)

# 单次创建计划最多生成的任务数, 避免用户填了一年导致生成 365 条
MAX_TASKS_PER_PLAN = 60
TASK_TITLE_TEMPLATE = "{subject} 第 {day} 天复习"


def build_task_templates(subject: str, start: date, end: date) -> list[StudyPlanTask]:
    """把 [start, end] 拆成每日任务(不写库, 只构造对象)。"""
    if end < start:
        raise BadRequestError("结束日期不能早于开始日期")

    total_days = (end - start).days + 1
    generate_days = min(total_days, MAX_TASKS_PER_PLAN)

    tasks: list[StudyPlanTask] = []
    for day_index in range(1, generate_days + 1):
        tasks.append(
            StudyPlanTask(
                title=TASK_TITLE_TEMPLATE.format(subject=subject, day=day_index),
                day_index=day_index,
                scheduled_date=start + timedelta(days=day_index - 1),
                status=TASK_STATUS_PENDING,
            )
        )
    return tasks


class StudyPlanService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------- 查询 -----------------------------
    def list_plans(self, user_id: int) -> list[StudyPlan]:
        stmt = (
            select(StudyPlan)
            .options(selectinload(StudyPlan.tasks))
            .where(StudyPlan.user_id == user_id)
            .order_by(StudyPlan.created_at.desc(), StudyPlan.id.desc())
        )
        return list(self.db.execute(stmt).scalars().unique().all())

    def get_plan(self, plan_id: int, user_id: int) -> StudyPlan:
        stmt = (
            select(StudyPlan)
            .options(selectinload(StudyPlan.tasks))
            .where(StudyPlan.id == plan_id)
        )
        plan = self.db.execute(stmt).scalars().unique().one_or_none()
        # 他人的计划与不存在的计划返回同样的 404
        if plan is None or plan.user_id != user_id:
            raise NotFoundError("学习计划不存在")
        return plan

    def get_task(self, task_id: int, user_id: int) -> StudyPlanTask:
        task = self.db.get(StudyPlanTask, task_id)
        if task is None:
            raise NotFoundError("任务不存在")
        # 用任务的 plan 反查归属, 防止越权改别人的任务
        plan = self.db.get(StudyPlan, task.plan_id)
        if plan is None or plan.user_id != user_id:
            raise NotFoundError("任务不存在")
        return task

    # ----------------------------- 变更 -----------------------------
    def create_plan(
        self,
        user_id: int,
        *,
        title: str,
        subject: str,
        start_date: date,
        end_date: date,
        daily_minutes: int = 60,
        note: str | None = None,
    ) -> StudyPlan:
        if end_date < start_date:
            raise BadRequestError("结束日期不能早于开始日期")

        plan = StudyPlan(
            user_id=user_id,
            title=title.strip(),
            subject=subject.strip(),
            start_date=start_date,
            end_date=end_date,
            daily_minutes=daily_minutes,
            note=note,
            status=PLAN_STATUS_ACTIVE,
        )
        plan.tasks = build_task_templates(plan.subject, start_date, end_date)

        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def update_plan(self, plan_id: int, user_id: int, **fields: object) -> StudyPlan:
        plan = self.get_plan(plan_id, user_id)
        for key, value in fields.items():
            if value is not None and hasattr(plan, key):
                setattr(plan, key, value)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def delete_plan(self, plan_id: int, user_id: int) -> None:
        plan = self.get_plan(plan_id, user_id)
        self.db.delete(plan)  # 任务由 cascade 一起删除
        self.db.commit()

    def update_task(
        self,
        task_id: int,
        user_id: int,
        *,
        status: str | None = None,
        note: str | None = None,
    ) -> StudyPlanTask:
        task = self.get_task(task_id, user_id)
        if status is not None:
            if status not in (TASK_STATUS_PENDING, TASK_STATUS_DONE):
                raise BadRequestError("任务状态只能是 pending 或 done")
            task.status = status
        if note is not None:
            task.note = note

        plan = self.db.get(StudyPlan, task.plan_id)
        if plan is not None:
            done = sum(1 for item in plan.tasks if item.status == TASK_STATUS_DONE)
            # 全部任务完成时自动把计划标记为 done
            if plan.tasks and done == len(plan.tasks):
                plan.status = PLAN_STATUS_DONE
            elif plan.status == PLAN_STATUS_DONE:
                plan.status = PLAN_STATUS_ACTIVE

        self.db.commit()
        self.db.refresh(task)
        return task

    # ----------------------------- 统计 -----------------------------
    def stats(self, user_id: int) -> dict[str, float | int]:
        plan_total = int(
            self.db.execute(
                select(func.count(StudyPlan.id)).where(StudyPlan.user_id == user_id)
            ).scalar_one()
            or 0
        )
        plan_active = int(
            self.db.execute(
                select(func.count(StudyPlan.id)).where(
                    StudyPlan.user_id == user_id,
                    StudyPlan.status == PLAN_STATUS_ACTIVE,
                )
            ).scalar_one()
            or 0
        )

        # 任务维度: 与计划表关联后按用户过滤
        task_total, task_done = self.db.execute(
            select(
                func.count(StudyPlanTask.id),
                func.coalesce(
                    func.sum(case((StudyPlanTask.status == TASK_STATUS_DONE, 1), else_=0)),
                    0,
                ),
            )
            .join(StudyPlan, StudyPlan.id == StudyPlanTask.plan_id)
            .where(StudyPlan.user_id == user_id)
        ).one()

        task_total = int(task_total or 0)
        task_done = int(task_done or 0)
        rate = round(task_done / task_total * 100, 1) if task_total else 0.0

        return {
            "plan_total": plan_total,
            "plan_active": plan_active,
            "task_total": task_total,
            "task_done": task_done,
            "completion_rate": rate,
        }


def to_plan_out(plan: StudyPlan) -> dict[str, object]:
    """把 ORM 计划对象转成响应所需的字典(含任务统计与进度)。"""
    tasks = list(plan.tasks)
    total = len(tasks)
    done = sum(1 for task in tasks if task.status == TASK_STATUS_DONE)
    return {
        "id": plan.id,
        "title": plan.title,
        "subject": plan.subject,
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "daily_minutes": plan.daily_minutes,
        "status": plan.status,
        "progress": round(done / total * 100, 1) if total else 0.0,
        "task_total": total,
        "task_done": done,
        "created_at": plan.created_at,
    }
