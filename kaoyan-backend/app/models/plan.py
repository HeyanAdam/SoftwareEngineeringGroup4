"""学习规划相关模型: 计划与阶段任务。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

PLAN_STATUS_ACTIVE = "active"
PLAN_STATUS_DONE = "done"
TASK_STATUS_PENDING = "pending"
TASK_STATUS_DONE = "done"


class StudyPlan(Base):
    """一份学习计划(如「数学强化 30 天」)。"""

    __tablename__ = "study_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, comment="科目")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=PLAN_STATUS_ACTIVE, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tasks: Mapped[list["StudyPlanTask"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StudyPlanTask.day_index",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StudyPlan id={self.id} title={self.title!r}>"


class StudyPlanTask(Base):
    """计划下的每日/阶段任务。"""

    __tablename__ = "study_plan_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("study_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False, comment="第几天")
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=TASK_STATUS_PENDING, nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)

    plan: Mapped["StudyPlan"] = relationship(back_populates="tasks", lazy="noload")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StudyPlanTask id={self.id} title={self.title!r}>"
