"""RBAC 授权模型: sys_role / sys_permission / sys_user_role / sys_role_permission。

四张表的字段、类型、长度、唯一约束全部按《权限表》表2~表5 来, 未增删任何一列。

关系:
    sys_user  --(sys_user_role)-->  sys_role
    sys_role  --(sys_role_permission)-->  sys_permission

role_name 在权限表里的字典值是「考研学生、系统管理员」两个初始角色;
L3 要求角色可增删改, 因此这里不做数据库层枚举约束, 只在初始化数据里写入这两个,
后台新增的自定义角色名同样合法(见 docs/改造说明.md「超出权限表的扩展」一节)。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import BigIntPK

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User


class Role(Base):
    """角色表 sys_role。"""

    __tablename__ = "sys_role"

    role_id: Mapped[int] = mapped_column(
        BigIntPK, primary_key=True, autoincrement=True, comment="角色唯一编号"
    )
    role_name: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, comment="角色名称, 不可重复"
    )
    role_desc: Mapped[str | None] = mapped_column(String(200), comment="角色功能描述")

    users: Mapped[list["User"]] = relationship(
        secondary="sys_user_role", back_populates="roles", lazy="selectin"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary="sys_role_permission", back_populates="roles", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Role role_id={self.role_id} role_name={self.role_name!r}>"


class Permission(Base):
    """权限定义表 sys_permission。"""

    __tablename__ = "sys_permission"

    perm_id: Mapped[int] = mapped_column(
        BigIntPK, primary_key=True, autoincrement=True, comment="权限唯一编号"
    )
    perm_key: Mapped[str] = mapped_column(
        String(80),
        unique=True,
        nullable=False,
        comment="权限标识符, 格式为 模块:操作, 如 studyplan:add",
    )
    perm_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="权限中文名称")
    module_name: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="所属业务模块, 后台按它分组展示"
    )

    roles: Mapped[list[Role]] = relationship(
        secondary="sys_role_permission", back_populates="permissions", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Permission perm_id={self.perm_id} perm_key={self.perm_key!r}>"


class UserRole(Base):
    """用户-角色中间表 sys_user_role。"""

    __tablename__ = "sys_user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uk_user_role"),)

    id: Mapped[int] = mapped_column(
        BigIntPK, primary_key=True, autoincrement=True, comment="中间记录主键"
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_role.role_id", ondelete="CASCADE"), nullable=False
    )


class RolePermission(Base):
    """角色-权限中间表 sys_role_permission。"""

    __tablename__ = "sys_role_permission"
    __table_args__ = (UniqueConstraint("role_id", "perm_id", name="uk_role_perm"),)

    id: Mapped[int] = mapped_column(
        BigIntPK, primary_key=True, autoincrement=True, comment="中间记录主键"
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_role.role_id", ondelete="CASCADE"), nullable=False
    )
    perm_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("sys_permission.perm_id", ondelete="CASCADE"), nullable=False
    )
