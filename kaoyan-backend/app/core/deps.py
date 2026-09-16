"""FastAPI 依赖注入。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User

# auto_error=False: 缺少请求头时由我们自己抛统一格式的 401, 而不是 FastAPI 默认的 {"detail": ...}
bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """从 Authorization: Bearer <token> 解析出当前用户。"""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("请先登录")

    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise UnauthorizedError("登录状态已过期, 请重新登录")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("登录凭证无效")

    user = db.get(User, int(user_id))
    if user is None:
        raise UnauthorizedError("用户不存在或已被删除")
    if not user.is_active:
        raise ForbiddenError("账号已被禁用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
