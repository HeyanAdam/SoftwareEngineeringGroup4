"""应用入口: 创建 FastAPI 实例、配置 CORS、注册各模块路由。

启动:
    uvicorn app.main:app --reload --port 8001

本次改造新增:
    * 启动时校验 SECRET_KEY(示例密钥 + 生产环境直接拒绝启动);
    * 启动时写入 RBAC 初始数据(角色/权限/管理员, 幂等);
    * 注册后台授权管理路由 /api/admin/*。
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import assert_secret_key_safe, assert_store_safe, settings
from app.core.database import check_connection, create_all, get_db
from app.core.exceptions import register_exception_handlers
from app.core.seed import seed_rbac
from app.modules.ai_chat.router import router as ai_router
from app.modules.file.router import router as file_router
from app.modules.rbac.router import router as rbac_router
from app.modules.study_plan.router import router as plan_router
from app.modules.user.router import router as user_router

logger = logging.getLogger("kaoyan")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """启动时建表、写入初始授权数据并探活数据库; 失败只告警, 不阻断启动。"""
    logger.info("服务启动中: %s", settings.APP_NAME)

    # 鉴权自检: 示例密钥、KV 存储(REDIS) 在生产环境不达标就直接拒绝启动
    assert_secret_key_safe()
    assert_store_safe()

    if settings.AUTO_CREATE_TABLES:
        try:
            create_all()
            logger.info("数据库表检查完成")
        except Exception as exc:  # noqa: BLE001
            logger.warning("自动建表失败(数据库没启动?): %s", exc)

    if settings.AUTO_SEED:
        from app.core.database import get_session_factory

        session = get_session_factory()()
        try:
            summary = seed_rbac(session)
            logger.info(
                "授权初始数据就绪: 角色 %d 个, 权限 %d 条",
                summary["roles"],
                summary["permissions"],
            )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            logger.warning("授权初始数据写入失败: %s", exc)
        finally:
            session.close()

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
    version="0.3.0",
    lifespan=lifespan,
)

# 允许前端跨域(开发期允许本地 5173; 生产请在 .env 里改成真实域名)
_origins = settings.cors_origin_list
# 浏览器不允许「Access-Control-Allow-Origin: *」与携带凭证同时出现,
# 配成 * 时直接关掉 credentials, 避免上线后请求被浏览器拦掉又查不出原因
_allow_credentials = "*" not in _origins
if not _allow_credentials:
    logger.warning("CORS_ORIGINS 配成 *, 已自动关闭 allow_credentials")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 统一异常响应格式
register_exception_handlers(app)

# 注册各模块路由
app.include_router(user_router)
app.include_router(rbac_router)
app.include_router(ai_router)
app.include_router(plan_router)
app.include_router(file_router)

# 仅开发环境提供文件上传测试页; 不再把整个 backend 目录挂成静态资源,
# 避免源码 / .env / sql 脚本通过 /static 被直接下载。
_STATIC_DIR = Path(__file__).resolve().parents[1]


@app.get("/static/file_test.html", include_in_schema=False)
def file_test_page() -> FileResponse:
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not Found")
    page = _STATIC_DIR / "file_test.html"
    if not page.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(page)


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
            for value in obj.values():
                _walk(value)
        elif isinstance(obj, list):
            for value in obj:
                _walk(value)

    _walk(schema)
    app.openapi_schema = schema
    return schema


app.openapi = _fix_openapi_file_schema


@app.get("/", tags=["系统"], summary="服务自检")
def read_root() -> dict[str, str]:
    return {"message": f"{settings.APP_NAME} - 后端启动成功", "docs": "/docs"}


@app.get("/api/db-check", tags=["系统"], summary="数据库连接测试")
def db_check(db: Session = Depends(get_db)) -> dict[str, str]:
    """返回当前数据库版本, 用于确认数据库配置是否正确。"""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Not Found")
    db_label = "SQLite" if settings.USE_SQLITE else "MySQL"
    try:
        version = check_connection()
        return {
            "status": "ok",
            "message": f"成功连接 {db_label}",
            "db_version": version,
            "database": ("(本地文件)" if settings.USE_SQLITE else settings.DB_NAME),
        }
    except Exception as exc:  # noqa: BLE001  这里要把失败原因展示给开发者
        if settings.USE_SQLITE:
            hint = "请确认 USE_SQLITE=true 且对数据目录有写权限"
        else:
            hint = (
                f"请确认 MySQL 已启动且 .env 中 DB_PORT={settings.DB_PORT} 正确"
                "(docker compose 映射到宿主机 3307)"
            )
        return {
            "status": "error",
            "message": f"{db_label} 连接失败: {exc}",
            "hint": hint,
        }
