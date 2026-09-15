"""仪表盘聚合服务: 真实 DB 统计 + 按日趋势, 结果经 Redis 缓存。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.models.chat import ChatMessage
from app.models.file import StoredFile
from app.models.rbac import Role, UserRole
from app.models.stats import DailyStat
from app.models.user import User
from app.schemas.common import DashboardOverview, DashboardSeriesPoint, DashboardStat

logger = get_logger(__name__)
CACHE_KEY = "cache:dashboard:overview"


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def overview(self, *, days: int = 30, use_cache: bool = True) -> DashboardOverview:
        redis = get_redis()
        if use_cache:
            try:
                raw = await redis.get(CACHE_KEY)
                if raw:
                    return DashboardOverview.model_validate(json.loads(raw))
            except Exception as exc:  # noqa: BLE001
                logger.debug("dashboard_cache_read_skipped", error=str(exc))

        data = await self._build(days)

        try:
            await redis.set(
                CACHE_KEY,
                json.dumps(data.model_dump(mode="json"), default=str),
                ex=settings.CACHE_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("dashboard_cache_write_skipped", error=str(exc))
        return data

    async def _build(self, days: int) -> DashboardOverview:
        user_total, user_active, user_new_7d = await self._user_stats()
        file_count, storage_bytes = await self._file_stats()
        message_count = await self._scalar(select(func.count()).select_from(ChatMessage))
        role_names = await self._role_lookup()
        role_rows = (
            await self.db.execute(
                select(UserRole.c.role_id, func.count(UserRole.c.user_id)).group_by(
                    UserRole.c.role_id
                )
            )
        ).all()

        trend_metric = "active_users"
        trend_rows = (
            await self.db.execute(
                select(DailyStat.stat_date, DailyStat.value)
                .where(
                    DailyStat.metric == trend_metric,
                    DailyStat.dimension == "all",
                    DailyStat.stat_date >= (datetime.now(UTC).date() - timedelta(days=days)),
                )
                .order_by(DailyStat.stat_date)
            )
        ).all()

        category_rows = (
            await self.db.execute(
                select(DailyStat.metric, func.sum(DailyStat.value))
                .where(DailyStat.dimension == "category")
                .group_by(DailyStat.metric)
                .order_by(func.sum(DailyStat.value).desc())
                .limit(8)
            )
        ).all()

        delta = self._trend_delta([int(v) for _, v in trend_rows])

        stats = [
            DashboardStat(key="users", label="用户总数", value=user_total, unit="人", delta=None),
            DashboardStat(key="active_users", label="活跃用户", value=user_active, unit="人"),
            DashboardStat(key="new_users_7d", label="近 7 日新增", value=user_new_7d, unit="人"),
            DashboardStat(key="files", label="文件总数", value=file_count, unit="个"),
            DashboardStat(
                key="storage",
                label="存储用量",
                value=round(storage_bytes / 1024 / 1024, 2),
                unit="MB",
            ),
            DashboardStat(key="messages", label="消息总数", value=message_count, unit="条"),
            DashboardStat(key="trend_delta", label="活跃趋势", value=delta, unit="%"),
        ]

        return DashboardOverview(
            stats=stats,
            trend=[DashboardSeriesPoint(label=f"{d:%m-%d}", value=float(v)) for d, v in trend_rows],
            categories=[
                DashboardSeriesPoint(label=str(metric), value=float(value or 0))
                for metric, value in category_rows
            ],
            role_distribution=[
                DashboardSeriesPoint(
                    label=role_names.get(role_id, f"role-{role_id}"), value=float(count)
                )
                for role_id, count in role_rows
            ],
            generated_at=datetime.now(UTC),
            extra={"trend_metric": trend_metric, "days": days},
        )

    # ------------------------------------------------------------------
    async def _scalar(self, stmt) -> int:  # noqa: ANN001
        return int((await self.db.execute(stmt)).scalar_one() or 0)

    async def _user_stats(self) -> tuple[int, int, int]:
        total = await self._scalar(select(func.count()).select_from(User))
        active = await self._scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
        since = datetime.now(UTC) - timedelta(days=7)
        new_7d = await self._scalar(
            select(func.count()).select_from(User).where(User.created_at >= since)
        )
        return total, active, new_7d

    async def _file_stats(self) -> tuple[int, int]:
        result = (
            await self.db.execute(select(func.count(), func.coalesce(func.sum(StoredFile.size), 0)))
        ).one()
        return int(result[0]), int(result[1] or 0)

    async def _role_lookup(self) -> dict[int, str]:
        rows = (await self.db.execute(select(Role.id, Role.name))).all()
        return {int(role_id): name for role_id, name in rows}

    @staticmethod
    def _trend_delta(values: list[int]) -> float:
        if len(values) < 4:
            return 0.0
        half = len(values) // 2
        first = sum(values[:half]) or 1
        second = sum(values[half:])
        return round((second - first) / first * 100, 2)
