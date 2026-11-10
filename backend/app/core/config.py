"""应用配置: 全部来自环境变量 / .env 文件。

新增配置项的步骤:
    1. 在 .env.example 里加一行(带默认值与注释)
    2. 在下面的 Settings 里加同名属性

本次改造新增的配置集中在「鉴权 / 授权」「邮箱验证码」「邮件通道」三节,
原有配置项的名字与默认值一律保持不变, 避免影响已有部署。
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from dotenv import load_dotenv

# 读取仓库内的 .env(不存在则忽略, 全部走默认值)
load_dotenv()

logger = logging.getLogger("kaoyan.config")

# 仓库里自带的示例密钥。生产环境还用它 = 任何人都能伪造 token
DEFAULT_SECRET_KEY = "dev-only-change-me-please-0123456789abcdef"


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

    # 本地快速验证用 SQLite; 生产 / docker-compose 设 USE_SQLITE=false 走 MySQL
    USE_SQLITE: bool = _env_bool("USE_SQLITE", True)
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
    # 启动时写入角色/权限/管理员初始数据(幂等, 已存在则跳过)
    AUTO_SEED: bool = _env_bool("AUTO_SEED", True)

    # ---------------- Redis ----------------
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = _env_int("REDIS_PORT", 6379)
    REDIS_DB: int = _env_int("REDIS_DB", 0)
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    # Redis 连不上时自动退化为进程内内存存储(仅单进程有效), 保证离线也能演示
    REDIS_ENABLED: bool = _env_bool("REDIS_ENABLED", True)

    # ---------------- MinIO ----------------
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "kaoyan")
    MINIO_SECURE: bool = _env_bool("MINIO_SECURE", False)

    # ---------------- 认证 (JWT / AuthX) ----------------
    SECRET_KEY: str = os.getenv("SECRET_KEY", DEFAULT_SECRET_KEY)
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = _env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    PASSWORD_MIN_LENGTH: int = _env_int("PASSWORD_MIN_LENGTH", 8)
    PASSWORD_MAX_LENGTH: int = _env_int("PASSWORD_MAX_LENGTH", 64)

    # 连续登录失败达到次数后锁定一段时间(单位: 次 / 秒)
    LOGIN_FAIL_LIMIT: int = _env_int("LOGIN_FAIL_LIMIT", 5)
    LOGIN_LOCK_SECONDS: int = _env_int("LOGIN_LOCK_SECONDS", 600)

    # ---------------- 授权 (RBAC) ----------------
    # 内置角色编号: 1 = 考研学生, 2 = 系统管理员(与初始化数据保持一致)
    DEFAULT_STUDENT_ROLE_ID: int = _env_int("DEFAULT_STUDENT_ROLE_ID", 1)
    ADMIN_ROLE_ID: int = _env_int("ADMIN_ROLE_ID", 2)
    # 权限查询结果缓存时间(秒); 角色/权限变更时会主动失效
    RBAC_CACHE_TTL: int = _env_int("RBAC_CACHE_TTL", 300)

    # ---------------- 邮箱验证码 ----------------
    EMAIL_CODE_TTL_SECONDS: int = _env_int("EMAIL_CODE_TTL_SECONDS", 300)
    EMAIL_CODE_MAX_ATTEMPTS: int = _env_int("EMAIL_CODE_MAX_ATTEMPTS", 5)
    # 同一邮箱两次发送的最小间隔, 防刷
    EMAIL_CODE_RESEND_SECONDS: int = _env_int("EMAIL_CODE_RESEND_SECONDS", 60)

    # ---------------- 图形验证码(密码登录防机器人) ----------------
    # 同一账号密码登录失败达到该次数后, 强制要求图形验证码
    CAPTCHA_AFTER_FAILURES: int = _env_int("CAPTCHA_AFTER_FAILURES", 2)
    CAPTCHA_TTL_SECONDS: int = _env_int("CAPTCHA_TTL_SECONDS", 300)

    # ---------------- 邮件通道 (QQ 邮箱 SMTP) ----------------
    MAIL_ENABLED: bool = _env_bool("MAIL_ENABLED", False)
    MAIL_HOST: str = os.getenv("MAIL_HOST", "smtp.qq.com")
    MAIL_PORT: int = _env_int("MAIL_PORT", 465)
    MAIL_USE_SSL: bool = _env_bool("MAIL_USE_SSL", True)
    MAIL_USERNAME: str = os.getenv("MAIL_USERNAME", "")
    # QQ 邮箱的「授权码」, 不是登录密码
    MAIL_PASSWORD: str = os.getenv("MAIL_PASSWORD", "")
    MAIL_FROM_NAME: str = os.getenv("MAIL_FROM_NAME", "考研AI导学平台")
    # SMTP 未配置或发送失败时, 是否退回控制台回显(生产环境强制关闭)
    MAIL_FALLBACK_CONSOLE: bool = _env_bool("MAIL_FALLBACK_CONSOLE", True)

    # ---------------- 初始化管理员 ----------------
    ADMIN_LOGIN_NAME: str = os.getenv("ADMIN_LOGIN_NAME", "admin")
    ADMIN_INITIAL_PASSWORD: str = os.getenv("ADMIN_INITIAL_PASSWORD", "Admin@123456")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "admin@example.com")

    # ---------------- 派生属性 ----------------
    @property
    def database_url(self) -> str:
        """SQLAlchemy 连接串。

        本地快速验证可用 SQLite (USE_SQLITE=true)；
        生产 / docker-compose 环境设 USE_SQLITE=false 走 MySQL。
        """
        if self.USE_SQLITE:
            return "sqlite:///./app_local.db"
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

    @property
    def admin_role_ids(self) -> set[int]:
        return {self.ADMIN_ROLE_ID}

    @property
    def mail_configured(self) -> bool:
        return bool(self.MAIL_USERNAME and self.MAIL_PASSWORD)

    @property
    def mail_fallback_allowed(self) -> bool:
        """是否允许把验证码回显出来(控制台 + 接口响应)。

        只在非生产环境生效: 生产环境把验证码返回给前端等于把邮箱验证码登录废掉。
        """
        return self.MAIL_FALLBACK_CONSOLE and not self.is_production

    @property
    def token_expire_seconds(self) -> int:
        return self.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def assert_store_safe() -> None:
    """生产环境必须启用 Redis。

    吊销名单与密码版本(pv)都存在 KV 存储里; 只落进程内存时, 服务一重启,
    改密前签发的旧令牌会重新可用, 等于改密失效机制形同虚设。
    """
    if settings.is_production and not settings.REDIS_ENABLED:
        raise RuntimeError(
            "生产环境必须启用 Redis(REDIS_ENABLED=true): 令牌吊销名单与密码版本依赖它, "
            "否则服务重启后旧令牌会重新生效。"
        )


def assert_secret_key_safe() -> None:
    """启动自检: 示例密钥 + 生产环境 直接拒绝启动。

    原来 .env 里就是仓库自带的示例值, 等于任何人都能签发出合法 token,
    这是整套鉴权里最严重的一个洞。
    """
    if settings.SECRET_KEY != DEFAULT_SECRET_KEY:
        return
    if settings.is_production:
        raise RuntimeError(
            "SECRET_KEY 仍是仓库自带的示例值, 生产环境禁止启动。"
            ' 生成方式: python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )
    logger.warning(
        "SECRET_KEY 仍是示例值, 任何人都能伪造 token; 上线前务必替换(见 .env.example)"
    )
