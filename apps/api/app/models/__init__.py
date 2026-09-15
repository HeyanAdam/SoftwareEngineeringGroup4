"""ORM 模型统一导出 (alembic autogenerate 依赖此处的显式导入)。"""

from app.models.chat import ChatMessage, ChatRoom
from app.models.file import StoredFile
from app.models.rbac import (
    Permission,
    Role,
    UserRole,
    permission_table,
    role_permission_table,
)
from app.models.stats import DailyStat
from app.models.user import User

__all__ = [
    "ChatMessage",
    "ChatRoom",
    "DailyStat",
    "Permission",
    "Role",
    "StoredFile",
    "User",
    "UserRole",
    "permission_table",
    "role_permission_table",
]
