"""Pydantic 基础模型与通用 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """可从 ORM 对象直接校验的基类。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class Msg(BaseModel):
    """简单消息响应。"""

    message: str = Field(default="ok", examples=["ok"])


class IdResponse(BaseModel):
    id: int


class ApiResponse(BaseModel, Generic[T]):
    """需要显式包装时的响应模型 (正常情况下由异常处理器/端点直接返回)。"""

    code: int = 0
    message: str = "ok"
    data: T | None = None


class TimestampedOut(ORMModel):
    created_at: datetime
    updated_at: datetime


class DashboardSeriesPoint(BaseModel):
    label: str
    value: float


class DashboardStat(BaseModel):
    key: str
    label: str
    value: float
    unit: str | None = None
    delta: float | None = None


class DashboardOverview(BaseModel):
    stats: list[DashboardStat]
    trend: list[DashboardSeriesPoint]
    categories: list[DashboardSeriesPoint]
    role_distribution: list[DashboardSeriesPoint]
    generated_at: datetime
    extra: dict[str, Any] = Field(default_factory=dict)
