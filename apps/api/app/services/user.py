"""用户管理服务 (管理员视角) 与个人信息维护。"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.cache import invalidate
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.pagination import PageParams
from app.core.security import hash_password
from app.models.rbac import Role
from app.models.user import User

logger = get_logger(__name__)

SORTABLE = {"id", "username", "email", "created_at", "last_login_at"}


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    def _base_query(self) -> Select[tuple[User]]:
        return select(User).options(selectinload(User.roles))

    async def list_users(
        self,
        params: PageParams,
        *,
        keyword: str | None = None,
        is_active: bool | None = None,
        role: str | None = None,
        sort_by: str = "-created_at",
    ) -> tuple[list[User], int]:
        stmt = self._base_query()

        if keyword:
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(
                    User.username.like(like),
                    User.email.like(like),
                    User.full_name.like(like),
                )
            )
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        if role:
            stmt = stmt.join(User.roles).where(Role.code == role)

        total = (
            await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
        ).scalar_one()

        field = sort_by.lstrip("-")
        column = getattr(User, field if field in SORTABLE else "created_at")
        stmt = stmt.order_by(column.desc() if sort_by.startswith("-") else column.asc())
        rows = (
            (await self.db.execute(stmt.offset(params.offset).limit(params.limit)))
            .scalars()
            .unique()
            .all()
        )
        return list(rows), int(total)

    async def get(self, user_id: int) -> User:
        user = (
            await self.db.execute(self._base_query().where(User.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError("用户不存在")
        return user

    async def list_roles(self) -> list[Role]:
        return list((await self.db.execute(select(Role).order_by(Role.id))).scalars().all())

    async def _resolve_roles(self, codes: list[str]) -> list[Role]:
        if not codes:
            return []
        roles = (await self.db.execute(select(Role).where(Role.code.in_(codes)))).scalars().all()
        missing = set(codes) - {r.code for r in roles}
        if missing:
            raise ConflictError(f"角色不存在: {', '.join(sorted(missing))}")
        return list(roles)

    async def create(
        self,
        *,
        username: str,
        email: str,
        password: str,
        full_name: str | None = None,
        is_active: bool = True,
        roles: list[str] | None = None,
    ) -> User:
        exists = (
            await self.db.execute(
                select(User.id).where(
                    or_(User.username == username, func.lower(User.email) == email.lower())
                )
            )
        ).first()
        if exists:
            raise ConflictError("用户名或邮箱已存在")

        user = User(
            username=username,
            email=email.lower(),
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=is_active,
        )
        user.roles = await self._resolve_roles(roles or [])
        self.db.add(user)
        await self.db.commit()
        await invalidate("users")
        return await self.get(user.id)

    async def update(self, user_id: int, data: dict, *, roles: list[str] | None = None) -> User:
        user = await self.get(user_id)
        for key, value in data.items():
            if value is not None and hasattr(user, key):
                setattr(user, key, value)
        if roles is not None:
            user.roles = await self._resolve_roles(roles)
        await self.db.commit()
        await invalidate("users")
        return await self.get(user_id)

    async def delete(self, user_id: int, *, operator_id: int) -> None:
        if user_id == operator_id:
            raise ConflictError("不能删除当前登录账号")
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("用户不存在")
        if user.is_superuser:
            remaining = (
                await self.db.execute(
                    select(func.count()).select_from(User).where(User.is_superuser.is_(True))
                )
            ).scalar_one()
            if remaining <= 1:
                raise ConflictError("必须保留至少一个超级管理员")
        await self.db.delete(user)
        await self.db.commit()
        await invalidate("users")
        logger.info("user_deleted", user_id=user_id, operator_id=operator_id)

    async def toggle_active(self, user_id: int) -> User:
        user = await self.get(user_id)
        user.is_active = not user.is_active
        await self.db.commit()
        return user

    async def reset_password(self, user_id: int, new_password: str) -> None:
        user = await self.get(user_id)
        user.hashed_password = hash_password(new_password)
        user.token_version += 1
        await self.db.commit()

    async def assign_roles(self, user_id: int, codes: list[str]) -> User:
        user = await self.get(user_id)
        user.roles = await self._resolve_roles(codes)
        await self.db.commit()
        return await self.get(user_id)

    # ------------------------------------------------------------------
    async def stats(self) -> dict[str, int]:
        total = (await self.db.execute(select(func.count()).select_from(User))).scalar_one()
        active = (
            await self.db.execute(
                select(func.count()).select_from(User).where(User.is_active.is_(True))
            )
        ).scalar_one()
        admins = (
            await self.db.execute(
                select(func.count()).select_from(User).where(User.is_superuser.is_(True))
            )
        ).scalar_one()
        return {
            "total": int(total),
            "active": int(active),
            "disabled": int(total - active),
            "superusers": int(admins),
        }
