"""Schema 转换助手 (避免在接口层重复拼装)。"""

from __future__ import annotations

from app.models.user import User
from app.schemas.auth import UserListItem


def to_list_item(user: User) -> UserListItem:
    return UserListItem(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        avatar=user.avatar,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        roles=user.role_codes,
    )
