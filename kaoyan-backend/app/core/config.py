"""应用配置: 全部来自环境变量 / .env 文件。

新增配置项的步骤:
    1. 在 .env.example 里加一行(带默认值与注释)
    2. 在下面的 Settings 里加同名属性
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

# 读取仓库内的 .env(不存在则忽略, 全部走默认值)
load_dotenv()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings:
    """运行期配置。"""

    # ---------------- 应用 ----------------
    APP_NAME: str = os.getenv("APP_NAME", "考研AI导学平台")
    DEBUG: bool = _env_bool("DEBUG", True)
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT: int = _env_int("BACKEND_PORT", 8001)

    # 允许跨域的前端地址, 逗号分隔; "*" 表示不限制(仅开发期使用)
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )

    # ---------------- MySQL ----------------
    # 注意: docker-compose.yml 把容器的 3306 映射到宿主机 3307
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = _env_int("DB_PORT", 3307)
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "kaoyan123")
    DB_NAME: str = os.getenv("DB_NAME", "kaoyan")
    DB_ECHO: bool = _env_bool("DB_ECHO", False)

    # 启动时自动建表(开发期方便; 表结构稳定后改用 alembic 迁移)
    AUTO_CREATE_TABLES: bool = _env_bool("AUTO_CREATE_TABLES", True)

    # ---------------- Redis ----------------
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = _env_int("REDIS_PORT", 6379)
    REDIS_DB: int = _env_int("REDIS_DB", 0)
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # ---------------- MinIO ----------------
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "kaoyan")
    MINIO_SECURE: bool = _env_bool("MINIO_SECURE", False)

    # ---------------- 认证 ----------------
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "dev-only-change-me-please-0123456789abcdef"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    PASSWORD_MIN_LENGTH: int = _env_int("PASSWORD_MIN_LENGTH", 6)

    # ---------------- 派生属性 ----------------
    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串(同步驱动 PyMySQL)。"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.CORS_ORIGINS.replace(" ", "")
        if raw == "*":
            return ["*"]
        return [item for item in raw.split(",") if item]

    @property
    def is_production(self) -> bool:
        return os.getenv("APP_ENV", "development").lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
