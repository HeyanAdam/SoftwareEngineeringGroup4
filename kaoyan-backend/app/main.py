"""应用入口: 创建 FastAPI 实例、配置 CORS、注册各模块路由。

启动:
    uvicorn app.main:app --reload --port 8001
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import check_connection, create_all, get_db
from app.core.exceptions import register_exception_handlers
from app.modules.ai_chat.router import router as ai_router
from app.modules.file.router import router as file_router
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
        description="考研 AI 导学平台后端接口。所有响应统一返回 {code, message, data} 结构。",
    version="0.2.0",
    lifespan=lifespan,
)

# 允许前端跨域(开发期允许本地 5173; 生产请在 .env 里改成真实域名)
app.add_middleware(
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
app.include_router(file_router)

# 挂载项目根目录为静态文件, 方便通过 /static/file_test.html 访问测试页面
_STATIC_DIR = Path(__file__).resolve().parents[1]
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# 修复 Swagger UI 文件上传控件不显示的问题
# FastAPI 0.141+ 生成的 schema 用 contentMediaType, Swagger UI 需要 format:binary
def _fix_openapi_file_schema():
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    def _walk(obj):
        if isinstance(obj, dict):
            if "contentMediaType" in obj and obj.get("type") == "string":
                obj["format"] = "binary"
                obj.pop("contentMediaType", None)
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)
    _walk(schema)
    app.openapi_schema = schema
    return schema

app.openapi = _fix_openapi_file_schema


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
