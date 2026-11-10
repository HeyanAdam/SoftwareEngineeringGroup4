"""ORM 模型包。

导入本包即完成全部 mapper 注册, ``create_all()`` 才能看到所有表。
本次改造新增 account / audit / rbac 三个模块; 原有 chat / file / plan / user 的定义不动。
"""

from __future__ import annotations

from app.models.account import UserAccount
from app.models.audit import AuditLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

# 原有业务模型: 仅导入以完成注册, 不做任何改动
from app.models import chat, file, plan  # noqa: F401

__all__ = [
    "AuditLog",
    "Permission",
    "Role",
    "RolePermission",
    "User",
    "UserAccount",
    "UserRole",
    "chat",
    "file",
    "plan",
]
