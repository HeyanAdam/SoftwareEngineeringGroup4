"""审计写入工具。

刻意做成「写失败也不影响主流程」: 审计是旁路, 主业务已经 commit 过了,
这里出错只打日志, 不让用户看到 500。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditAction:
    """审计动作名。

    统一在这里定义, 前端 AuditLogView 的 ACTION_LABELS 与之逐条对应;
    两边任何一侧新增动作都要同步, 否则日志页会显示原始英文键。
    """

    USER_REGISTER = "user.register"
    LOGIN_SUCCESS = "login.success"
    LOGIN_FAILURE = "login.failure"
    LOGOUT = "logout"
    PASSWORD_RESET = "password.reset"
    PASSWORD_CHANGE = "password.change"
    ROLE_CREATE = "role.create"
    ROLE_UPDATE = "role.update"
    ROLE_DELETE = "role.delete"
    ROLE_PERMISSION_UPDATE = "role.permission.update"
    USER_ROLE_UPDATE = "user.role.update"
    USER_STATUS_UPDATE = "user.status.update"


def client_ip(request: Request | None) -> str | None:
    """取来源 IP: 优先 X-Forwarded-For 第一段(经 Nginx 转发时)。"""
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def write_audit(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
    request: Request | None = None,
    success: bool = True,
    login_name: str | None = None,
) -> None:
    """写一条 sys_audit_log; 自身异常不外抛。"""
    try:
        db.add(
            AuditLog(
                user_id=user.id if user is not None else None,
                login_name=(user.username if user is not None else login_name),
                action=action,
                target_type=target_type,
                target_id=str(target_id) if target_id is not None else None,
                detail=detail,
                ip=client_ip(request),
                success=success,
            )
        )
        db.commit()
    except Exception:  # pragma: no cover - 旁路失败不影响主流程
        db.rollback()
        logger.exception("写审计日志失败: action=%s", action)
