"""后台授权管理接口(对应禅道「组织 - 权限管理」)。

所有接口都在服务端做权限判定, 前端菜单隐藏只是体验优化。
    /api/admin/roles            role:manage
    /api/admin/permissions      perm:view
    /api/admin/users            user:manage
    /api/admin/audit-logs       role:manage
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.deps import DbSession
from app.core.rbac import require_permission
from app.models.user import User
from app.modules.rbac.service import RbacService
from app.schemas.rbac import (
    AccountStatusUpdateRequest,
    AdminUserOut,
    AuditLogPage,
    PermissionGroupOut,
    RoleBrief,
    RoleCreateRequest,
    RolePermissionUpdateRequest,
    RoleOut,
    RoleUpdateRequest,
    UserRoleUpdateRequest,
)

router = APIRouter(prefix="/api/admin", tags=["后台授权管理"])

RoleManager = Annotated[User, Depends(require_permission("role:manage"))]
UserManager = Annotated[User, Depends(require_permission("user:manage"))]
PermViewer = Annotated[User, Depends(require_permission("perm:view"))]


# ----------------------------- 角色 -----------------------------
@router.get("/roles", response_model=list[RoleOut], summary="角色列表")
def list_roles(db: DbSession, _: RoleManager) -> list[RoleOut]:
    return RbacService(db).list_roles()


@router.post("/roles", response_model=RoleOut, summary="新增角色")
def create_role(
    payload: RoleCreateRequest, db: DbSession, operator: RoleManager, request: Request
) -> RoleOut:
    return RbacService(db).create_role(
        payload.role_name, payload.role_desc, operator, request
    )


@router.put("/roles/{role_id}", response_model=RoleOut, summary="修改角色")
def update_role(
    role_id: int,
    payload: RoleUpdateRequest,
    db: DbSession,
    operator: RoleManager,
    request: Request,
) -> RoleOut:
    return RbacService(db).update_role(
        role_id, payload.role_name, payload.role_desc, operator, request
    )


@router.delete("/roles/{role_id}", summary="删除角色")
def delete_role(
    role_id: int, db: DbSession, operator: RoleManager, request: Request
) -> dict[str, str]:
    RbacService(db).delete_role(role_id, operator, request)
    return {"message": "角色已删除"}


# ----------------------------- 权限 -----------------------------
@router.get(
    "/permissions", response_model=list[PermissionGroupOut], summary="权限清单(按模块分组)"
)
def list_permissions(db: DbSession, _: PermViewer) -> list[PermissionGroupOut]:
    return RbacService(db).list_permission_groups()


@router.get(
    "/roles/{role_id}/permissions",
    response_model=list[int],
    summary="某角色已授权的权限编号",
)
def get_role_permissions(role_id: int, db: DbSession, _: RoleManager) -> list[int]:
    return RbacService(db).role_permission_ids(role_id)


@router.put(
    "/roles/{role_id}/permissions",
    response_model=list[int],
    summary="保存角色权限勾选结果(整体覆盖)",
)
def update_role_permissions(
    role_id: int,
    payload: RolePermissionUpdateRequest,
    db: DbSession,
    operator: RoleManager,
    request: Request,
) -> list[int]:
    return RbacService(db).update_role_permissions(
        role_id, payload.perm_ids, operator, request
    )


# ----------------------------- 用户 -----------------------------
@router.get("/users", summary="用户列表(含角色)")
def list_users(
    db: DbSession,
    _: UserManager,
    keyword: str | None = Query(default=None, description="按登录名/邮箱模糊搜索"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    return RbacService(db).list_users(keyword, page, size)


@router.put(
    "/users/{user_id}/roles",
    response_model=list[RoleBrief],
    summary="给用户分配角色(多角色)",
)
def update_user_roles(
    user_id: int,
    payload: UserRoleUpdateRequest,
    db: DbSession,
    operator: UserManager,
    request: Request,
) -> list[RoleBrief]:
    return RbacService(db).update_user_roles(
        user_id, payload.role_ids, operator, request
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserOut,
    summary="启用 / 禁用账号",
)
def update_user_status(
    user_id: int,
    payload: AccountStatusUpdateRequest,
    db: DbSession,
    operator: UserManager,
    request: Request,
) -> AdminUserOut:
    return RbacService(db).update_user_status(
        user_id, payload.account_status, operator, request
    )


# ----------------------------- 审计日志 -----------------------------
@router.get("/audit-logs", response_model=AuditLogPage, summary="审计日志(按时间倒序)")
def list_audit_logs(
    db: DbSession,
    _: RoleManager,
    action: str | None = Query(default=None, max_length=50, description="动作标识精确匹配"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> AuditLogPage:
    """按时间倒序分页; action 为空表示全部动作。"""
    return RbacService(db).list_audit_logs(action, page, size)


__all__ = ["router"]
