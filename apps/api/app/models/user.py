"""用户模型。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.file import StoredFile
    from app.models.rbac import Role


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(191), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    avatar: Mapped[str | None] = mapped_column(String(512))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 令牌版本: 改密码/强制下线时 +1, 使旧 refresh token 失效
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    remark: Mapped[str | None] = mapped_column(String(255))

    roles: Mapped[list[Role]] = relationship(
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )
    files: Mapped[list[StoredFile]] = relationship(back_populates="owner", lazy="noload")

    # ------------------------------------------------------------------
    @property
    def role_codes(self) -> list[str]:
        return [role.code for role in self.roles]

    @property
    def permissions(self) -> set[str]:
        perms: set[str] = set()
        for role in self.roles:
            perms.update(role.permission_codes)
        return perms

    def has_role(self, *codes: str) -> bool:
        owned = set(self.role_codes)
        return bool(owned.intersection(codes)) if codes else bool(owned)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r}>"
