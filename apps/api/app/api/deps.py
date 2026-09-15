"""FastAPI 依赖: 数据库会话、当前用户、权限校验、限流。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.rate_limit import check_rate_limit
from app.core.redis import redis_dependency
from app.core.security import decode_token
from app.models.user import User
from app.services.auth import AuthService

logger = get_logger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(redis_dependency)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise UnauthorizedError("缺少访问令牌")
    payload = decode_token(token, expected_type="access")
    user = await AuthService(db).get_active_user(int(payload["sub"]))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise ForbiddenError("需要超级管理员权限")
    return user


SuperUser = Annotated[User, Depends(get_current_superuser)]


def require_roles(*role_codes: str):
    """依赖工厂: 要求当前用户拥有任一角色。"""

    async def _checker(user: CurrentUser) -> User:
        if user.is_superuser or user.has_role(*role_codes):
            return user
        raise ForbiddenError(f"需要以下角色之一: {', '.join(role_codes)}")

    return _checker


def require_permissions(*permission_codes: str):
    """依赖工厂: 要求当前用户拥有任一权限点 (超级管理员直通)。"""

    async def _checker(user: CurrentUser) -> User:
        if user.is_superuser:
            return user
        owned = user.permissions
        if owned.intersection(permission_codes):
            return user
        raise ForbiddenError(f"需要以下权限之一: {', '.join(permission_codes)}")

    return _checker


async def rate_limit_dependency(request: Request) -> None:
    await check_rate_limit(request)


RateLimited = Annotated[None, Depends(rate_limit_dependency)]
