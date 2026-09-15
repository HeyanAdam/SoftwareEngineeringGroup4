"""按日聚合统计 (仪表盘趋势图数据源)。

生产环境由定时任务/ETL 写入; 演示环境由 initial_data 预置近 30 天数据。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Date, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class DailyStat(Base, TimestampMixin):
    __tablename__ = "daily_stats"
    __table_args__ = (Index("ix_daily_stats_date_metric", "stat_date", "metric"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stat_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    # 指标名: active_users / api_calls / uploads / storage_bytes ...
    # (metric 同时作为 ECharts 饼图的分类名)
    metric: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # 维度标签, 如平台/渠道
    dimension: Mapped[str] = mapped_column(String(48), default="all", nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DailyStat {self.stat_date} {self.metric}={self.value}>"
