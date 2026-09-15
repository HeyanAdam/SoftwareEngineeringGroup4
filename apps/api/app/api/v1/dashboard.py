"""仪表盘 / ECharts 数据接口。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.core.cache import invalidate
from app.schemas.common import DashboardOverview, Msg
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get(
    "/overview", response_model=DashboardOverview, summary="总览: 指标卡 + 趋势 + 分类 + 角色分布"
)
async def overview(
    db: DbSession,
    _: CurrentUser,
    days: int = Query(default=30, ge=7, le=180, description="趋势区间天数"),
    refresh: bool = Query(default=False, description="true 时绕过缓存"),
) -> DashboardOverview:
    return await DashboardService(db).overview(days=days, use_cache=not refresh)


@router.post("/cache/refresh", response_model=Msg, summary="清除仪表盘缓存")
async def refresh_cache(_: CurrentUser) -> Msg:
    removed = await invalidate("dashboard")
    return Msg(message=f"已清除 {removed} 个缓存键")
