"""FastAPI 应用入口。

启动顺序 (lifespan):
    1. 配置日志
    2. 校验依赖连通性 (MySQL / Redis / MinIO) —— 失败仅告警, 不阻塞启动
    3. 建表 (AUTO_CREATE_TABLES) + 种子数据 (SEED_DEMO_DATA)
    4. 启动 Redis Pub/Sub 监听任务, 支撑多实例 WebSocket 广播
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import dispose_engine, init_models
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware
from app.core.minio_client import ensure_bucket
from app.core.redis import close_redis
from app.core.redis import ping as redis_ping
from app.ws.manager import INSTANCE_ID, pubsub_listener
from app.ws.routes import router as ws_router

configure_logging()
logger = get_logger("app")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "app_starting",
        app=settings.APP_NAME,
        env=settings.APP_ENV,
        version=settings.APP_VERSION,
        instance=INSTANCE_ID,
    )

    if settings.AUTO_CREATE_TABLES:
        try:
            await init_models()
            logger.info("tables_ready")
        except Exception as exc:  # noqa: BLE001
            logger.error("init_models_failed", error=str(exc), exc_info=True)

    try:
        await ensure_bucket()
    except Exception as exc:  # noqa: BLE001
        logger.warning("minio_bucket_not_ready", error=str(exc))

    if settings.SEED_DEMO_DATA:
        try:
            from app.initial_data import seed

            await seed()
        except Exception as exc:  # noqa: BLE001
            logger.warning("seed_failed", error=str(exc))

    if not await redis_ping():
        logger.warning("redis_unavailable_ws_broadcast_degraded")

    stop_event = asyncio.Event()
    listener = asyncio.create_task(pubsub_listener(stop_event), name="ws-pubsub-listener")
    app.state.pubsub_stop = stop_event
    app.state.pubsub_task = listener

    logger.info("app_started", docs=settings.docs_url)
    try:
        yield
    finally:
        stop_event.set()
        listener.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await listener
        await close_redis()
        await dispose_engine()
        logger.info("app_stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Vue3 + FastAPI + MySQL + Redis + MinIO + WebSocket 脚手架后端",
    docs_url=settings.docs_url,
    redoc_url=None,
    openapi_url=settings.openapi_url,
    lifespan=lifespan,
    default_response_class=JSONResponse,
)

# ------------------------------ 中间件 (后添加的先执行) ------------------------------
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(RequestContextMiddleware)
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time-Ms"],
        max_age=600,
    )

register_exception_handlers(app)

# ------------------------------ 路由 ------------------------------
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router)  # WebSocket 挂在 /ws


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url=settings.docs_url or f"{settings.API_V1_PREFIX}/health/live")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
