"""FastAPI 依赖注入: 数据库会话、当前登录用户、权限校验。

令牌校验交给 AuthX(get_token_from_request + verify_token), 但异常在这里统一转换成
项目的 {code, message, data} 结构, 避免前端要同时处理两套错误格式。

关键修复(改造前的问题):
    * 用 HTTPBearer(auto_error=False) + 自己 decode, 令牌无法吊销 —— 现在退出登录会把
      令牌写进 Redis 吊销名单, 立即失效;
    * 403 只在前端拦截器清 token, 后端没有任何"账号被禁用后 token 立刻不可用"的机制 ——
      现在每个请求都校验 account_status。
"""

from __future__ import annotations

from typing import Annotated

from authx import JWTDecodeError, TokenExpiredError
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import is_token_revoked, password_version, verify_access_token
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


def read_bearer_token(request: Request) -> str | None:
    """从 Authorization: Bearer <token> 取原始令牌, 没有则返回 None。

    为什么不用 auth.get_token_from_request:
        该方法在 AuthX 1.7.1 里是 async 的, 而本依赖是同步函数(会跑在线程池里)。
        为了不让同步的数据库会话阻塞事件循环, 这里按同一套 header 规则自己解析;
        真正决定令牌是否合法的解码与验签仍然走 AuthX.verify_token。
    """
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = credentials.strip()
    return token or None


def get_current_user(request: Request, db: DbSession) -> User:
    """解析当前登录用户。未登录 / 令牌失效 / 账号被禁用都会抛对应异常。"""
    token = read_bearer_token(request)
    if not token:
        raise UnauthorizedError("请先登录")

    if is_token_revoked(token):
        raise UnauthorizedError("登录状态已失效, 请重新登录")

    try:
        payload = verify_access_token(token)
    except TokenExpiredError as exc:
        raise UnauthorizedError("登录状态已过期, 请重新登录") from exc
    except JWTDecodeError as exc:
        raise UnauthorizedError("登录凭证无效, 请重新登录") from exc
    except Exception as exc:  # noqa: BLE001  兜底: 任何解析失败都视为未登录
        raise UnauthorizedError("登录凭证无效, 请重新登录") from exc

    subject = payload.sub
    if not subject:
        raise UnauthorizedError("登录凭证无效, 请重新登录")

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("登录凭证无效, 请重新登录") from exc

    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("用户不存在或已被删除")
    if user.account_status != 1:
        raise ForbiddenError("账号已被禁用, 请联系管理员")

    # 密码版本校验: 改密 / 重置密码后, 旧令牌里的 pv 与当前版本不一致 -> 立即失效
    token_pv = (payload.model_extra or {}).get("pv", 0)
    if int(token_pv or 0) != password_version(user.id):
        raise UnauthorizedError("密码已修改, 请重新登录")

    # 退出登录时要用到原始令牌
    request.state.access_token = token
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
