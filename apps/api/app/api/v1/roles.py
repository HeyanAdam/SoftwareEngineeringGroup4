"""角色与权限管理接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, SuperUser, require_permissions
from app.core.exceptions import ConflictError, NotFoundError
from app.models.rbac import Permission, Role
from app.schemas.common import IdResponse
from app.schemas.role import PermissionOut, RoleCreate, RoleOut, RoleUpdate

router = APIRouter(prefix="/roles", tags=["角色权限"])

CanWrite = Depends(require_permissions("roles:write"))


def _to_out(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        description=role.description,
        is_builtin=role.is_builtin,
        permissions=role.permission_codes,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


async def _resolve_permissions(db: DbSession, codes: list[str]) -> list[Permission]:
    if not codes:
        return []
    rows = (await db.execute(select(Permission).where(Permission.code.in_(codes)))).scalars().all()
    missing = set(codes) - {row.code for row in rows}
    if missing:
        raise ConflictError(f"权限点不存在: {', '.join(sorted(missing))}")
    return list(rows)


@router.get("", response_model=list[RoleOut], summary="角色列表")
async def list_roles(db: DbSession) -> list[RoleOut]:
    rows = (
        (await db.execute(select(Role).options(selectinload(Role.permissions)).order_by(Role.id)))
        .scalars()
        .all()
    )
    return [_to_out(role) for role in rows]


@router.get("/permissions", response_model=list[PermissionOut], summary="权限点全量列表")
async def list_permissions(db: DbSession) -> list[PermissionOut]:
    rows = (
        (await db.execute(select(Permission).order_by(Permission.module, Permission.sort)))
        .scalars()
        .all()
    )
    return [PermissionOut.model_validate(row) for row in rows]


@router.post(
    "",
    response_model=RoleOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建角色",
    dependencies=[CanWrite],
)
async def create_role(payload: RoleCreate, db: DbSession, _: SuperUser) -> RoleOut:
    if (await db.execute(select(Role.id).where(Role.code == payload.code))).first():
        raise ConflictError(f"角色 code 已存在: {payload.code}")
    role = Role(code=payload.code, name=payload.name, description=payload.description)
    role.permissions = await _resolve_permissions(db, payload.permissions)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return _to_out(role)


@router.patch(
    "/{role_id}",
    response_model=RoleOut,
    summary="更新角色",
    dependencies=[CanWrite],
)
async def update_role(role_id: int, payload: RoleUpdate, db: DbSession, _: SuperUser) -> RoleOut:
    role = await db.get(Role, role_id)
    if role is None:
        raise NotFoundError("角色不存在")
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    permission_codes = data.pop("permissions", None)
    for key, value in data.items():
        setattr(role, key, value)
    if permission_codes is not None:
        role.permissions = await _resolve_permissions(db, permission_codes)
    await db.commit()
    await db.refresh(role)
    return _to_out(role)


@router.delete(
    "/{role_id}",
    response_model=IdResponse,
    summary="删除角色",
    dependencies=[CanWrite],
)
async def delete_role(role_id: int, db: DbSession, _: SuperUser) -> IdResponse:
    role = await db.get(Role, role_id)
    if role is None:
        raise NotFoundError("角色不存在")
    if role.is_builtin:
        raise ConflictError("内置角色不允许删除")
    in_use = (
        await db.execute(
            select(func.count()).select_from(Role).join(Role.users).where(Role.id == role_id)
        )
    ).scalar_one()
    if in_use:
        raise ConflictError(f"仍有 {in_use} 个用户使用该角色, 请先解绑")
    await db.delete(role)
    await db.commit()
    return IdResponse(id=role_id)
