"""授权(后台管理)业务逻辑。

对应禅道 L3 的能力集合:
    * 角色 CRUD(内置角色不可删, 自定义角色可增删改);
    * 权限按 module_name 分组展示 + 勾选授权/回收(差量更新, 记审计);
    * 用户多角色分配、账号启停;

几条防呆规则(避免管理员把自己锁死):
    * 不能修改自己的角色;
    * 不能禁用自己的账号;
    * 内置角色(1 考研学生 / 2 系统管理员)不允许删除;
    * 角色下还有用户时不允许删除, 先解除分配。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.audit import AuditAction, write_audit
from app.core.rbac import invalidate_permission_cache
from app.models.audit import AuditLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.schemas.rbac import (
    AdminUserOut,
    AuditLogOut,
    PermissionGroupOut,
    PermissionOut,
    RoleBrief,
    RoleOut,
)

logger = logging.getLogger("kaoyan.rbac")

BUILT_IN_ROLE_IDS: frozenset[int] = frozenset({1, 2})


class RbacService:
    """后台授权管理。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------- 角色 -----------------------------
    def list_roles(self) -> list[RoleOut]:
        roles = list(self.db.scalars(select(Role).order_by(Role.role_id)).all())

        counts = dict(
            self.db.execute(
                select(UserRole.role_id, func.count()).group_by(UserRole.role_id)
            ).all()
        )

        return [
            RoleOut(
                role_id=role.role_id,
                role_name=role.role_name,
                role_desc=role.role_desc,
                user_count=int(counts.get(role.role_id, 0)),
                permission_ids=sorted(perm.perm_id for perm in role.permissions),
                built_in=role.role_id in BUILT_IN_ROLE_IDS,
            )
            for role in roles
        ]

    def create_role(
        self, role_name: str, role_desc: str | None, operator: User, request: Request | None
    ) -> RoleOut:
        if self.db.scalar(select(Role).where(Role.role_name == role_name)):
            raise ConflictError("该角色名称已存在")

        role = Role(role_name=role_name, role_desc=role_desc)
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)

        write_audit(
            self.db,
            action=AuditAction.ROLE_CREATE,
            user=operator,
            target_type="role",
            target_id=role.role_id,
            detail={"role_name": role.role_name, "role_desc": role.role_desc},
            request=request,
        )
        return RoleOut(
            role_id=role.role_id,
            role_name=role.role_name,
            role_desc=role.role_desc,
            user_count=0,
            permission_ids=[],
            built_in=False,
        )

    def update_role(
        self,
        role_id: int,
        role_name: str | None,
        role_desc: str | None,
        operator: User,
        request: Request | None,
    ) -> RoleOut:
        role = self._get_role(role_id)
        before = {"role_name": role.role_name, "role_desc": role.role_desc}

        if role_name and role_name != role.role_name:
            if self.db.scalar(select(Role).where(Role.role_name == role_name)):
                raise ConflictError("该角色名称已存在")
            role.role_name = role_name
        if role_desc is not None:
            role.role_desc = role_desc

        self.db.commit()

        write_audit(
            self.db,
            action=AuditAction.ROLE_UPDATE,
            user=operator,
            target_type="role",
            target_id=role.role_id,
            detail={
                "before": before,
                "after": {"role_name": role.role_name, "role_desc": role.role_desc},
            },
            request=request,
        )
        return next(item for item in self.list_roles() if item.role_id == role.role_id)

    def delete_role(self, role_id: int, operator: User, request: Request | None) -> None:
        role = self._get_role(role_id)
        if role.role_id in BUILT_IN_ROLE_IDS:
            raise BadRequestError("内置角色不允许删除")

        user_count = int(
            self.db.scalar(
                select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
            )
            or 0
        )
        if user_count:
            raise ConflictError(f"该角色下还有 {user_count} 个用户, 请先解除分配")

        # 先清掉角色-权限关系, 再删角色(用关系级 clear, 保持 ORM 状态一致)
        role.permissions.clear()
        self.db.flush()
        self.db.delete(role)
        self.db.commit()

        invalidate_permission_cache()
        write_audit(
            self.db,
            action=AuditAction.ROLE_DELETE,
            user=operator,
            target_type="role",
            target_id=role_id,
            detail={"role_name": role.role_name},
            request=request,
        )

    # ----------------------------- 权限 -----------------------------
    def list_permission_groups(self) -> list[PermissionGroupOut]:
        """按 module_name 分组返回, 顺序固定为权限表的模块顺序。"""
        module_order = [
            "择校模块",
            "刷题训练模块",
            "模考测评模块",
            "复试训练模块",
            "督学陪伴模块",
            "资讯政策模块",
            "后台管理模块",
        ]
        perms = list(
            self.db.scalars(select(Permission).order_by(Permission.perm_id)).all()
        )
        grouped: dict[str, list[PermissionOut]] = {name: [] for name in module_order}
        for perm in perms:
            grouped.setdefault(perm.module_name, []).append(
                PermissionOut(
                    perm_id=perm.perm_id,
                    perm_key=perm.perm_key,
                    perm_name=perm.perm_name,
                    module_name=perm.module_name,
                )
            )
        return [
            PermissionGroupOut(module_name=name, permissions=items)
            for name, items in grouped.items()
            if items
        ]

    def role_permission_ids(self, role_id: int) -> list[int]:
        role = self._get_role(role_id)
        return sorted(perm.perm_id for perm in role.permissions)

    def update_role_permissions(
        self,
        role_id: int,
        perm_ids: list[int],
        operator: User,
        request: Request | None,
    ) -> list[int]:
        role = self._get_role(role_id)

        valid_ids = set(
            self.db.scalars(
                select(Permission.perm_id).where(Permission.perm_id.in_(perm_ids))
            ).all()
        ) if perm_ids else set()
        unknown = set(perm_ids) - valid_ids
        if unknown:
            raise BadRequestError(f"存在无效的权限编号: {sorted(unknown)}")

        current = {perm.perm_id: perm.perm_key for perm in role.permissions}
        added = [
            {"perm_id": pid, "perm_key": self._perm_key(pid)}
            for pid in sorted(valid_ids - set(current))
        ]
        removed = [
            {"perm_id": pid, "perm_key": key} for pid, key in sorted(current.items()) if pid not in valid_ids
        ]

        role.permissions.clear()
        self.db.flush()
        for perm_id in sorted(valid_ids):
            self.db.add(RolePermission(role_id=role_id, perm_id=perm_id))
        self.db.commit()

        invalidate_permission_cache()
        write_audit(
            self.db,
            action=AuditAction.ROLE_PERMISSION_UPDATE,
            user=operator,
            target_type="role",
            target_id=role_id,
            detail={"added": added, "removed": removed},
            request=request,
        )
        return sorted(valid_ids)

    # ----------------------------- 用户 -----------------------------
    def list_users(
        self, keyword: str | None, page: int, size: int
    ) -> dict[str, Any]:
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            condition = User.username.like(pattern) | User.email.like(pattern)
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = list(
            self.db.scalars(
                stmt.order_by(User.id).offset((page - 1) * size).limit(size)
            ).all()
        )
        return {
            "total": total,
            "items": [
                AdminUserOut(
                    user_id=user.id,
                    login_name=user.username,
                    email=user.email,
                    account_status=user.account_status,
                    create_time=user.created_at,
                    roles=[
                        RoleBrief(role_id=role.role_id, role_name=role.role_name)
                        for role in sorted(user.roles, key=lambda r: r.role_id)
                    ],
                )
                for user in rows
            ],
        }

    def update_user_roles(
        self,
        user_id: int,
        role_ids: list[int],
        operator: User,
        request: Request | None,
    ) -> list[RoleBrief]:
        if user_id == operator.id:
            raise BadRequestError("不能修改自己的角色, 请让其他管理员操作")

        user = self._get_user(user_id)
        valid_ids = set(
            self.db.scalars(select(Role.role_id).where(Role.role_id.in_(role_ids))).all()
        ) if role_ids else set()
        unknown = set(role_ids) - valid_ids
        if unknown:
            raise BadRequestError(f"存在无效的角色编号: {sorted(unknown)}")

        before = sorted(role.role_id for role in user.roles)

        user.roles.clear()
        self.db.flush()
        for role_id in sorted(valid_ids):
            self.db.add(UserRole(user_id=user_id, role_id=role_id))
        self.db.commit()

        invalidate_permission_cache()
        write_audit(
            self.db,
            action=AuditAction.USER_ROLE_UPDATE,
            user=operator,
            target_type="user",
            target_id=user_id,
            detail={"before": before, "after": sorted(valid_ids)},
            request=request,
        )
        self.db.refresh(user)
        return [
            RoleBrief(role_id=role.role_id, role_name=role.role_name)
            for role in sorted(user.roles, key=lambda r: r.role_id)
        ]

    def update_user_status(
        self,
        user_id: int,
        account_status: int,
        operator: User,
        request: Request | None,
    ) -> AdminUserOut:
        if user_id == operator.id:
            raise BadRequestError("不能修改自己的账号状态")

        user = self._get_user(user_id)
        before = user.account_status
        user.account_status = account_status
        self.db.commit()

        write_audit(
            self.db,
            action=AuditAction.USER_STATUS_UPDATE,
            user=operator,
            target_type="user",
            target_id=user_id,
            detail={"before": before, "after": account_status},
            request=request,
        )
        return AdminUserOut(
            user_id=user.id,
            login_name=user.username,
            email=user.email,
            account_status=user.account_status,
            create_time=user.created_at,
            roles=[
                RoleBrief(role_id=role.role_id, role_name=role.role_name)
                for role in sorted(user.roles, key=lambda r: r.role_id)
            ],
        )

    # ----------------------------- 审计日志 -----------------------------
    def list_audit_logs(self, action: str | None, page: int, size: int) -> dict[str, Any]:
        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)
        if action:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = list(
            self.db.scalars(
                stmt.order_by(AuditLog.id.desc()).offset((page - 1) * size).limit(size)
            ).all()
        )
        return {
            "total": total,
            "items": [
                AuditLogOut(
                    id=row.id,
                    user_id=row.user_id,
                    login_name=row.login_name,
                    action=row.action,
                    target_type=row.target_type,
                    target_id=row.target_id,
                    detail=row.detail,
                    ip=row.ip,
                    success=row.success,
                    create_time=row.create_time,
                )
                for row in rows
            ],
        }

    # ----------------------------- 内部工具 -----------------------------
    def _get_role(self, role_id: int) -> Role:
        role = self.db.get(Role, role_id)
        if role is None:
            raise NotFoundError("角色不存在")
        return role

    def _get_user(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("用户不存在")
        return user

    def _perm_key(self, perm_id: int) -> str:
        perm = self.db.get(Permission, perm_id)
        return perm.perm_key if perm else str(perm_id)


def is_admin_role(role_id: int) -> bool:
    """是否为管理员角色(与 settings.ADMIN_ROLE_ID 保持一致)。"""
    return role_id in settings.admin_role_ids
