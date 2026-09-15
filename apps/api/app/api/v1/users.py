"""用户管理接口 (需 users:* 权限点或管理员角色)。"""

from __future__ import annotations

import secrets
import string
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, SuperUser, require_permissions
from app.core.exceptions import BadRequestError
from app.core.pagination import Page, PageParams, page_params
from app.schemas.auth import UserAdminUpdate, UserCreate, UserListItem
from app.schemas.common import IdResponse
from app.schemas.role import RoleAssign, RoleOut
from app.schemas.user_helpers import to_list_item
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["用户管理"])

# 读权限可用于「查看」类端点, 写权限用于变更类端点
CanRead = Depends(require_permissions("users:read"))
CanWrite = Depends(require_permissions("users:write"))


@router.get("", response_model=Page[UserListItem], summary="用户分页列表", dependencies=[CanRead])
async def list_users(
    db: DbSession,
    params: Annotated[PageParams, Depends(page_params)],
    keyword: str | None = Query(
        default=None, max_length=64, description="用户名/邮箱/姓名模糊搜索"
    ),
    is_active: bool | None = Query(default=None),
    role: str | None = Query(default=None, max_length=64, description="按角色 code 过滤"),
    sort_by: str = Query(default="-created_at", description="排序字段, 前缀 - 表示倒序"),
) -> Page[UserListItem]:
    rows, total = await UserService(db).list_users(
        params, keyword=keyword, is_active=is_active, role=role, sort_by=sort_by
    )
    return Page.create([to_list_item(user) for user in rows], total, params)


@router.get("/stats", summary="用户统计", dependencies=[CanRead])
async def user_stats(db: DbSession) -> dict[str, int]:
    return await UserService(db).stats()


@router.get(
    "/roles/options", response_model=list[RoleOut], summary="可选角色列表", dependencies=[CanRead]
)
async def role_options(db: DbSession) -> list[RoleOut]:
    roles = await UserService(db).list_roles()
    return [
        RoleOut(
            id=role.id,
            code=role.code,
            name=role.name,
            description=role.description,
            is_builtin=role.is_builtin,
            permissions=role.permission_codes,
            created_at=role.created_at,
            updated_at=role.updated_at,
        )
        for role in roles
    ]


@router.post(
    "",
    response_model=UserListItem,
    status_code=status.HTTP_201_CREATED,
    summary="创建用户",
    dependencies=[CanWrite],
)
async def create_user(payload: UserCreate, db: DbSession, _: SuperUser) -> UserListItem:
    user = await UserService(db).create(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        is_active=payload.is_active,
        roles=payload.roles,
    )
    return to_list_item(user)


@router.get("/{user_id}", response_model=UserListItem, summary="用户详情", dependencies=[CanRead])
async def get_user(user_id: int, db: DbSession) -> UserListItem:
    return to_list_item(await UserService(db).get(user_id))


@router.patch(
    "/{user_id}", response_model=UserListItem, summary="更新用户", dependencies=[CanWrite]
)
async def update_user(
    user_id: int, payload: UserAdminUpdate, db: DbSession, _: SuperUser
) -> UserListItem:
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    roles = data.pop("roles", None)
    if not data and roles is None:
        raise BadRequestError("没有需要更新的字段")
    user = await UserService(db).update(user_id, data, roles=roles)
    return to_list_item(user)


@router.put(
    "/{user_id}/roles", response_model=UserListItem, summary="分配角色", dependencies=[CanWrite]
)
async def assign_roles(
    user_id: int, payload: RoleAssign, db: DbSession, _: SuperUser
) -> UserListItem:
    return to_list_item(await UserService(db).assign_roles(user_id, payload.role_codes))


@router.post(
    "/{user_id}/toggle-active",
    response_model=UserListItem,
    summary="启用/禁用",
    dependencies=[CanWrite],
)
async def toggle_active(user_id: int, db: DbSession, _: SuperUser) -> UserListItem:
    return to_list_item(await UserService(db).toggle_active(user_id))


@router.post(
    "/{user_id}/reset-password",
    response_model=dict,
    summary="重置密码 (返回随机新密码)",
    dependencies=[CanWrite],
)
async def reset_password(user_id: int, db: DbSession, _: SuperUser) -> dict[str, str]:
    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(12))
    await UserService(db).reset_password(user_id, new_password)
    return {"password": new_password}


@router.delete("/{user_id}", response_model=IdResponse, summary="删除用户", dependencies=[CanWrite])
async def delete_user(user_id: int, db: DbSession, operator: SuperUser) -> IdResponse:
    await UserService(db).delete(user_id, operator_id=operator.id)
    return IdResponse(id=user_id)
