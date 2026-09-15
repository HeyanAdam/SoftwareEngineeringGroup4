"""应用配置: 全部通过环境变量注入 (12-factor), 见根目录 .env.example。"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 支持两种运行位置: apps/api/.env (本机裸跑) 与仓库根 .env (docker compose 注入)
        env_file=(".env", "../../.env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------- 应用 ----------------
    APP_NAME: str = "SG4 API"
    APP_ENV: Literal["local", "development", "staging", "production", "test"] = "local"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    # 容器名/版本号, 由 CI 注入
    APP_VERSION: str = "0.1.0"
    GIT_SHA: str = "dev"

    # ---------------- 数据库 (MySQL) ----------------
    DATABASE_URL: str = "mysql+aiomysql://sg4:sg4-change-me@127.0.0.1:3306/sg4?charset=utf8mb4"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800
    AUTO_CREATE_TABLES: bool = True
    SEED_DEMO_DATA: bool = True

    # ---------------- Redis ----------------
    REDIS_URL: str = "redis://:sg4-redis-change-me@127.0.0.1:6379/0"
    REDIS_MAX_CONNECTIONS: int = 50
    CACHE_TTL_SECONDS: int = 60

    # ---------------- MinIO / S3 ----------------
    MINIO_ENDPOINT: str = "127.0.0.1:9000"
    # 浏览器可直接访问的地址 (生成预签名 URL 用), 生产为 CDN/网关域名
    MINIO_PUBLIC_ENDPOINT: str | None = None
    MINIO_ACCESS_KEY: str = "sg4-minio"
    MINIO_SECRET_KEY: str = "sg4-minio-change-me"
    MINIO_BUCKET: str = "sg4-files"
    MINIO_SECURE: bool = False
    MINIO_REGION: str = "us-east-1"
    # 预签名 URL 有效期 (秒)
    MINIO_PRESIGN_EXPIRE: int = 3600
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_UPLOAD_TYPES: str = (
        "image/png,image/jpeg,image/gif,image/webp,application/pdf,"
        "text/plain,text/csv,application/zip,"
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    # ---------------- 认证 ----------------
    SECRET_KEY: str = "dev-only-secret-key-please-change-me-0123456789"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8
    # 登录失败锁定: 次数 / 窗口秒数
    LOGIN_MAX_ATTEMPTS: int = 10
    LOGIN_LOCK_SECONDS: int = 300

    # ---------------- CORS ----------------
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---------------- WebSocket ----------------
    WS_PATH: str = "/ws"
    WS_HEARTBEAT_SECONDS: int = 25
    WS_MAX_MESSAGE_BYTES: int = 64 * 1024

    # ---------------- 其它 ----------------
    RATE_LIMIT_PER_MINUTE: int = 600
    ENABLE_DOCS: bool = True

    # ------------------------------------------------------------------
    @field_validator("CORS_ORIGINS")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.CORS_ORIGINS.replace(" ", "")
        if raw == "*":
            return ["*"]
        return [item for item in raw.split(",") if item]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_upload_type_set(self) -> set[str]:
        return {
            item.strip().lower() for item in self.ALLOWED_UPLOAD_TYPES.split(",") if item.strip()
        }

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """alembic / 启动等待使用同步驱动。"""
        return (
            self.DATABASE_URL.replace("+aiomysql", "+pymysql")
            .replace("+asyncmy", "+pymysql")
            .replace("+asyncio", "")
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.APP_ENV in ("production", "staging")

    @property
    def docs_url(self) -> str | None:
        return f"{self.API_V1_PREFIX}/docs" if self.ENABLE_DOCS and not self.is_production else None

    @property
    def openapi_url(self) -> str | None:
        return (
            f"{self.API_V1_PREFIX}/openapi.json"
            if self.ENABLE_DOCS and not self.is_production
            else None
        )

    def model_post_init(self, __context: Any) -> None:  # pragma: no cover
        if self.is_production and "change-me" in self.SECRET_KEY:
            raise ValueError("生产环境必须设置安全的 SECRET_KEY (见 .env.example)")
        if self.MINIO_PUBLIC_ENDPOINT is None:
            object.__setattr__(self, "MINIO_PUBLIC_ENDPOINT", self.MINIO_ENDPOINT)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

__all__ = ["Settings", "get_settings", "settings", "Field"]
