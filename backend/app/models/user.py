"""系统登录账号表 sys_user(对应《权限表》表1)。

字段严格按权限表定义:
    user_id / login_name / password / account_status / create_time

相对原项目的改动:
    * 表名 users -> sys_user
    * id -> user_id, username -> login_name, password_hash -> password
    * is_active(bool) -> account_status(TINYINT, 1 启用 / 0 禁用)
    * created_at -> create_time, 删除 updated_at(权限表里没有这个字段)
    * email: 邮箱验证码登录必须按邮箱反查账号, 放在认证表里才能建唯一索引。
      它属于权限表之外的增量, 与 sys_audit_log 表、两张关联表的唯一约束一并
      在 docs/改造说明.md 第 10 节列明

属性名保留 id / username / password_hash:
    ORM 属性名与数据库列名解耦(mapped_column("login_name", ...)),
    这样 chat / plan / file 等既有模块里的 user.id、user.username 不用改。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, SmallInteger, String, text
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import BigIntPK


class User(Base):
    """登录账号 + 角色关联。业务画像字段在 user_account 表。"""

    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(
        "user_id", BigIntPK, primary_key=True, autoincrement=True, comment="登录账号唯一编号"
    )
    username: Mapped[str] = mapped_column(
        "login_name", String(50), unique=True, index=True, nullable=False, comment="登录用户名"
    )
    email: Mapped[str] = mapped_column(
        String(120),
        unique=True,
        index=True,
        nullable=False,
        comment="绑定邮箱, 用于邮箱验证码登录与找回密码",
    )
    password_hash: Mapped[str] = mapped_column(
        "password", String(128), nullable=False, comment="argon2 加密串, 禁止明文"
    )
    account_status: Mapped[int] = mapped_column(
        # 权限表写的是 TINYINT; SQLite 不支持 TINYINT, 用 with_variant 在 MySQL 侧落成 TINYINT
        SmallInteger().with_variant(TINYINT(), "mysql"),
        nullable=False,
        default=1,
        server_default="1",
        comment="账号状态: 0 禁用, 1 启用",
    )
    created_at: Mapped[datetime] = mapped_column(
        "create_time", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="创建时间"
    )

    # 一个账号一个业务档案; 档案在注册时一并创建
    account: Mapped["UserAccount | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", lazy="selectin"
    )
    # 多对多: 一个用户可以同时拥有多个角色(考研学生 + 系统管理员)
    roles: Mapped[list["Role"]] = relationship(
        secondary="sys_user_role", back_populates="users", lazy="selectin"
    )

    # ---------------- 兼容属性 ----------------
    @property
    def is_active(self) -> bool:
        return self.account_status == 1

    @property
    def nickname(self) -> str | None:
        return self.account.user_name if self.account and self.account.user_name else None

    @property
    def display_name(self) -> str:
        """优先展示昵称, 没有则用登录名。"""
        return self.nickname or self.username

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User user_id={self.id} login_name={self.username!r}>"


# 类型检查用(避免运行期循环导入)
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:  # pragma: no cover
    from app.models.account import UserAccount
    from app.models.rbac import Role
