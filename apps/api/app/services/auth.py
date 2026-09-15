"""认证与令牌服务。

刷新令牌采用「Redis 白名单 + jti」: 登出/改密码即失效, 支持多端会话追踪。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.core.security import (
    access_token_ttl_seconds,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    refresh_token_ttl_seconds,
    verify_password,
)
from app.models.rbac import Role
from app.models.user import User

logger = get_logger(__name__)

DEFAULT_ROLE_CODE = "viewer"
REFRESH_KEY = "auth:refresh:{jti}"
LOGIN_FAIL_KEY = "auth:fail:{identity}"


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # --------------------------- 查询 ---------------------------
    async def get_by_identity(self, identity: str) -> User | None:
        stmt = select(User).where(
            or_(User.username == identity, func.lower(User.email) == identity.lower())
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_active_user(self, user_id: int) -> User:
        user = await self.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("用户不存在", code=40104)
        if not user.is_active:
            raise ForbiddenError("账号已被禁用, 请联系管理员")
        return user

    async def get_role_by_code(self, code: str) -> Role | None:
        return (await self.db.execute(select(Role).where(Role.code == code))).scalar_one_or_none()

    # --------------------------- 注册 ---------------------------
    async def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        roles: list[str] | None = None,
        is_active: bool = True,
    ) -> User:
        exists = (
            await self.db.execute(
                select(User.id).where(
                    or_(User.username == username, func.lower(User.email) == email.lower())
                )
            )
        ).first()
        if exists:
            raise ConflictError("用户名或邮箱已被注册")

        user = User(
            username=username,
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=is_active,
        )

        role_codes = roles or [DEFAULT_ROLE_CODE]
        if role_codes:
            found = (
                (await self.db.execute(select(Role).where(Role.code.in_(role_codes))))
                .scalars()
                .all()
            )
            missing = set(role_codes) - {role.code for role in found}
            if missing:
                raise ConflictError(f"角色不存在: {', '.join(sorted(missing))}")
            user.roles = list(found)

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info("user_registered", user_id=user.id, username=user.username, roles=role_codes)
        return user

    # --------------------------- 登录 ---------------------------
    async def _guard_login_attempts(self, identity: str) -> None:
        redis = get_redis()
        try:
            count = await redis.get(LOGIN_FAIL_KEY.format(identity=identity.lower()))
        except Exception:  # noqa: BLE001
            return
        if count and int(count) >= settings.LOGIN_MAX_ATTEMPTS:
            ttl = await redis.ttl(LOGIN_FAIL_KEY.format(identity=identity.lower()))
            raise ForbiddenError(f"登录失败次数过多, 请 {max(ttl, 1)} 秒后重试")

    async def _record_login_failure(self, identity: str) -> None:
        redis = get_redis()
        key = LOGIN_FAIL_KEY.format(identity=identity.lower())
        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, settings.LOGIN_LOCK_SECONDS)
                await pipe.execute()
        except Exception:  # noqa: BLE001
            return

    async def _clear_login_failure(self, identity: str) -> None:
        try:
            await get_redis().delete(LOGIN_FAIL_KEY.format(identity=identity.lower()))
        except Exception:  # noqa: BLE001
            return

    async def authenticate(self, identity: str, password: str) -> User:
        await self._guard_login_attempts(identity)
        user = await self.get_by_identity(identity)
        if user is None or not verify_password(password, user.hashed_password):
            await self._record_login_failure(identity)
            raise UnauthorizedError("用户名或密码错误", code=40105)
        if not user.is_active:
            raise ForbiddenError("账号已被禁用, 请联系管理员")

        await self._clear_login_failure(identity)
        user.last_login_at = datetime.now(UTC)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # --------------------------- 令牌 ---------------------------
    async def issue_tokens(self, user: User) -> dict[str, object]:
        extra = {"username": user.username, "ver": user.token_version}
        access, _ = create_access_token(user.id, **extra)
        refresh, _ = create_refresh_token(user.id, **extra)
        payload = decode_token(refresh, expected_type="refresh")

        redis = get_redis()
        try:
            await redis.set(
                REFRESH_KEY.format(jti=payload["jti"]),
                str(user.id),
                ex=refresh_token_ttl_seconds(),
            )
        except Exception as exc:  # noqa: BLE001  Redis 不可用时降级为无状态
            logger.warning("refresh_token_store_failed", error=str(exc))

        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "bearer",
            "expires_in": access_token_ttl_seconds(),
        }

    async def refresh(self, refresh_token: str) -> dict[str, object]:
        payload = decode_token(refresh_token, expected_type="refresh")
        user = await self.get_active_user(int(payload["sub"]))
        if int(payload.get("ver", 0)) != user.token_version:
            raise UnauthorizedError("登录凭证已失效, 请重新登录", code=40106)

        key = REFRESH_KEY.format(jti=payload["jti"])
        redis = get_redis()
        try:
            if not await redis.exists(key):
                raise UnauthorizedError("刷新令牌已失效, 请重新登录", code=40107)
            await redis.delete(key)  # 一次性使用, 旋转令牌
        except UnauthorizedError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("refresh_token_check_skipped", error=str(exc))

        return await self.issue_tokens(user)

    async def logout(self, user: User) -> None:
        user.token_version += 1
        await self.db.commit()
        logger.info("user_logged_out", user_id=user.id)

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        if not verify_password(old_password, user.hashed_password):
            raise UnauthorizedError("原密码不正确", code=40108)
        if verify_password(new_password, user.hashed_password):
            raise ConflictError("新密码不能与原密码相同")
        user.hashed_password = hash_password(new_password)
        user.token_version += 1  # 强制其它端重新登录
        await self.db.commit()
        logger.info("password_changed", user_id=user.id)
