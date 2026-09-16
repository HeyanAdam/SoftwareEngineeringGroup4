"""学习规划模块的请求/响应模型。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    title: str
    day_index: int
    scheduled_date: date
    status: str = Field(description="pending = 未完成, done = 已完成")
    note: str | None = None


class PlanCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100, description="计划名称")
    subject: str = Field(min_length=1, max_length=50, description="科目, 如 数学/英语/政治/专业课")
    start_date: date
    end_date: date
    daily_minutes: int = Field(default=60, ge=10, le=720, description="每天计划学习分钟数")
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _check_dates(self) -> "PlanCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 364:
            raise ValueError("计划跨度不要超过一年")
        return self


class PlanUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, max_length=50)
    daily_minutes: int | None = Field(default=None, ge=10, le=720)
    status: str | None = Field(default=None, pattern="^(active|done|archived)$")
    note: str | None = Field(default=None, max_length=500)


class PlanOut(BaseModel):
    """列表用的计划摘要(带任务统计)。"""

    id: int
    title: str
    subject: str
    start_date: date
    end_date: date
    daily_minutes: int
    status: str
    progress: float = Field(description="完成百分比 0-100")
    task_total: int
    task_done: int
    created_at: datetime


class PlanDetailOut(PlanOut):
    """详情: 计划 + 任务列表。"""

    note: str | None = None
    tasks: list[TaskOut] = Field(default_factory=list)


class TaskUpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|done)$")
    note: str | None = Field(default=None, max_length=500)


class PlanStatsOut(BaseModel):
    plan_total: int
    plan_active: int
    task_total: int
    task_done: int
    completion_rate: float = Field(description="任务完成率 0-100")
