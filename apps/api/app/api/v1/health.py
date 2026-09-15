"""健康检查与运行时指标。"""

from __future__ import annotations

import platform
import sys
import time

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.minio_client import ensure_bucket
from app.core.redis import ping as redis_ping
from app.ws.manager import INSTANCE_ID, manager

router = APIRouter(tags=["health"])
STARTED_AT = time.time()

REQUEST_COUNTER = Counter("app_http_requests_total", "HTTP 请求总数", ["method", "path", "status"])
WS_GAUGE = Gauge("app_ws_connections", "当前 WebSocket 连接数")
UP_GAUGE = Gauge("app_up", "应用存活 (1=存活)")


@router.get("/health/live", summary="存活探针")
async def live() -> dict[str, object]:
    UP_GAUGE.set(1)
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
        "instance": INSTANCE_ID,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
    }


@router.get("/health/ready", summary="就绪探针 (依赖检查)")
async def ready() -> dict[str, object]:
    checks: dict[str, object] = {}

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["mysql"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["mysql"] = f"error: {type(exc).__name__}"

    checks["redis"] = "ok" if await redis_ping() else "error"

    try:
        await ensure_bucket()
        checks["minio"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["minio"] = f"error: {type(exc).__name__}"

    WS_GAUGE.set(manager.connection_count)
    checks["websocket_connections"] = manager.connection_count

    healthy = all(value == "ok" for key, value in checks.items() if key != "websocket_connections")
    return {"status": "ok" if healthy else "degraded", "checks": checks}


@router.get("/health/info", summary="运行时信息")
async def info() -> dict[str, object]:
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "git_sha": settings.GIT_SHA,
        "env": settings.APP_ENV,
        "debug": settings.DEBUG,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "instance": INSTANCE_ID,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "ws_connections": manager.connection_count,
        "ws_rooms": len(manager._rooms),  # noqa: SLF001 (只读诊断用途)
    }


@router.get("/metrics", summary="Prometheus 指标", include_in_schema=False)
async def metrics() -> PlainTextResponse:
    UP_GAUGE.set(1)
    WS_GAUGE.set(manager.connection_count)
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
