"""数据库连接: SQLAlchemy 引擎 / 会话工厂 / 建表 / 探活。

数据源为 ``settings.database_url``:
    * 本地默认 SQLite(./app_local.db), 开箱即用;
    * 生产 / docker-compose 设 USE_SQLITE=false 走 MySQL(见 .env.example)。

说明: 本文件属于 FastAPI 工程底座, 鉴权改造包未携带, 这里按调用方的
接口约定(Base / engine / get_db / get_session_factory / create_all /
check_connection)补齐。
"""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger("kaoyan.database")


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


def _build_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        # SQLite: 单文件库, check_same_thread=False 让连接可被依赖注入串行复用
        return create_engine(
            url,
            echo=settings.DB_ECHO,
            connect_args={"check_same_thread": False},
        )
    # MySQL: 打开连接探活与定时回收, 避免拿到被服务端断开的空闲连接
    return create_engine(
        url,
        echo=settings.DB_ECHO,
        pool_pre_ping=True,
        pool_recycle=3600,
    )


engine = _build_engine()

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine, autocommit=False, autoflush=False
)


def get_session_factory() -> sessionmaker[Session]:
    """返回会话工厂(启动期 seed 等场景使用)。"""
    return SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖: 每请求一个会话, 用毕即关。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """按已注册的模型建表(幂等)。开发期便利, 生产请改用 alembic。"""
    import app.models  # noqa: F401  导入即注册全部 mapper

    Base.metadata.create_all(bind=engine)


def check_connection() -> str:
    """探活数据库并返回版本字符串, 失败抛异常。"""
    with engine.connect() as conn:
        if engine.url.get_backend_name() == "sqlite":
            version = conn.execute(text("select sqlite_version()")).scalar()
            return f"SQLite {version}"
        version = conn.execute(text("SELECT VERSION()")).scalar()
        return str(version)
