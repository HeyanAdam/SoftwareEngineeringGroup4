"""Alembic 运行环境。

数据库 URL 解析优先级:
    1. 命令行覆盖:  alembic -x db_url=mysql+pymysql://... upgrade head
    2. 环境变量:    ALEMBIC_DATABASE_URL=...
    3. 应用配置:    app.core.config.settings.sync_database_url (由 DATABASE_URL 推导, 同步驱动)

这样 docker compose / .env 注入的 DATABASE_URL 既可被应用使用, 也可被迁移使用;
不需要在 alembic.ini 里重复维护连接串。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import SQLAlchemyError

# ruff 会把本目录当成 first-party 包, 因此 alembic.context 排在 sqlalchemy 之后
from alembic import context

# 保证任意 CWD 下都能 import app.* (alembic.ini 的 prepend_sys_path 只覆盖 CWD)
BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app import models  # noqa: E402,F401  导入以把所有表注册进 Base.metadata
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

config = context.config

# 使用 alembic.ini 的 [loggers] 配置, 但不关闭应用已配置的 logger
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# autogenerate 的对比基准
target_metadata = Base.metadata


def _to_sync_url(url: str) -> str:
    """异步驱动 -> 同步驱动 (迁移过程使用同步连接)。

    mysql+aiomysql -> mysql+pymysql; sqlite+aiosqlite -> sqlite (便于本地/测试)
    """
    return (
        url.replace("+aiomysql", "+pymysql")
        .replace("+asyncmy", "+pymysql")
        .replace("+aiosqlite", "")
    )


def _database_url() -> str:
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("db_url") or os.getenv("ALEMBIC_DATABASE_URL") or settings.sync_database_url
    return _to_sync_url(url)


def _masked(url: str) -> str:
    """隐藏密码, 便于安全地打印/记录。"""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}"


def run_migrations_offline() -> None:
    """离线模式: 只输出 SQL (alembic upgrade head --sql), 不连接数据库。"""
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=False,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式: 连接数据库并执行迁移。"""
    url = _database_url()
    section = dict(config.get_section(config.config_ini_section) or {})
    # 直接用 dict 传入, 避免 ConfigParser 对 URL 中 % 的插值问题
    section["sqlalchemy.url"] = url

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    except SQLAlchemyError as exc:
        # 容器入口脚本允许迁移失败继续启动, 这里给出清晰可读的原因
        raise SystemExit(
            "\n[alembic] 数据库迁移失败: "
            f"{type(exc).__name__}: {exc}\n"
            f"[alembic] 目标数据库: {_masked(url)}\n"
            "[alembic] 请确认数据库已就绪, 并检查 DATABASE_URL / ALEMBIC_DATABASE_URL。\n"
        ) from exc
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
