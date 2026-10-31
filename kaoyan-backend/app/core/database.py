"""数据库连接与会话管理。

设计要点:
    * 引擎与会话工厂是**懒加载**的: 模块导入时不会去连数据库, 只有真正用到才创建连接。
      这样单元测试或只跑静态检查时不会因为数据库没启动而报错。
    * get_db() 是 FastAPI 依赖, 每个请求一个会话, 用完自动关闭。
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine():
    """获取(或首次创建)全局引擎。"""
    global _engine
    if _engine is None:
        engine_kwargs = {
            "echo": settings.DB_ECHO,
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "future": True,
        }
        if settings.database_url.startswith("sqlite"):
            # FastAPI 的同步依赖可能在不同工作线程中使用连接。
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        _engine = create_engine(settings.database_url, **engine_kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的数据库会话。"""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    """按模型定义建表(已存在的表不会被修改)。"""
    from app import models  # noqa: F401  必须导入, 否则模型未注册到 Base.metadata

    Base.metadata.create_all(bind=get_engine())


def check_connection() -> str:
    """返回当前数据库类型和版本号, 用于连通性自检。"""
    from sqlalchemy import text

    engine = get_engine()
    sql = "SELECT sqlite_version()" if engine.dialect.name == "sqlite" else "SELECT VERSION()"
    with engine.connect() as conn:
        version = conn.execute(text(sql)).scalar()
    return f"{engine.dialect.name} {version}"
