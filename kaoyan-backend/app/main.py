"""应用入口: 创建 FastAPI 实例、配置 CORS、注册各模块路由。

启动:
    uvicorn app.main:app --reload --port 8001
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import check_connection, create_all, get_db
from app.core.exceptions import register_exception_handlers
from app.modules.ai_chat.router import router as ai_router
from app.modules.study_plan.router import router as plan_router
from app.modules.user.router import router as user_router

logger = logging.getLogger("kaoyan")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """启动时建表并探活数据库; 失败只告警, 不阻断启动(方便先写前端)。"""
    logger.info("服务启动中: %s", settings.APP_NAME)
    if settings.AUTO_CREATE_TABLES:
        try:
            create_all()
            logger.info("数据库表检查完成")
        except Exception as exc:  # noqa: BLE001
            logger.warning("自动建表失败(数据库没启动?): %s", exc)
    try:
        version = check_connection()
        logger.info("MySQL 连接正常, 版本: %s", version)
    except Exception as exc:  # noqa: BLE001
        logger.warning("MySQL 连接失败: %s", exc)
    yield
    logger.info("服务已停止")


app = FastAPI(
    title=f"{settings.APP_NAME} - 后端",
    description="考研 AI 导学平台后端接口。成功返回数据本身, 失败返回 {code, message, data}。",
    version="0.2.0",
    lifespan=lifespan,
)

# 允许前端跨域(开发期允许本地 5173; 生产请在 .env 里改成真实域名)
#app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一异常响应格式
register_exception_handlers(app)

# 注册各模块路由
app.include_router(user_router)
app.include_router(ai_router)
app.include_router(plan_router)


@app.get("/", tags=["系统"], summary="服务自检")
def read_root() -> dict[str, str]:
    return {"message": f"{settings.APP_NAME} - 后端启动成功", "docs": "/docs"}


@app.get("/api/db-check", tags=["系统"], summary="数据库连接测试")
def db_check(db: Session = Depends(get_db)) -> dict[str, str]:
    """返回当前 MySQL 版本, 用于确认数据库配置是否正确。"""
    try:
        version = check_connection()
        return {
            "status": "ok",
            "message": "成功连接 MySQL",
            "mysql_version": version,
            "database": settings.DB_NAME,
        }
    except Exception as exc:  # noqa: BLE001  这里要把失败原因展示给开发者
        return {
            "status": "error",
            "message": f"连接失败: {exc}",
            "hint": (
                f"请确认 MySQL 已启动且 .env 中 DB_PORT={settings.DB_PORT} 正确"
                "(docker compose 映射到宿主机 3307)"
            ),
        }
