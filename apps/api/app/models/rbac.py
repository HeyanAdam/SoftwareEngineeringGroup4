"""RBAC 模型: 角色 / 权限 / 用户-角色 / 角色-权限。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User

# 用户 <-> 角色 (多对多)
UserRole = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_builtin: Mapped[bool] = mapped_column(default=False, nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary=UserRole, back_populates="roles", lazy="noload"
    )
    permissions: Mapped[list[Permission]] = relationship(
        secondary="role_permissions", back_populates="roles", lazy="selectin"
    )

    @property
    def permission_codes(self) -> list[str]:
        return [perm.code for perm in self.permissions]

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Role code={self.code!r}>"


# 角色 <-> 权限 (多对多)
role_permission_table = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# 兼容别名 (外部按 *_table 命名引用)
permission_table = role_permission_table


class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("code", name="uq_permissions_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    module: Mapped[str] = mapped_column(String(48), index=True, default="common", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permission_table, back_populates="permissions", lazy="noload"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Permission code={self.code!r}>"
