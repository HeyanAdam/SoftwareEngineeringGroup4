"""权限解析与校验。

原则(和《明文密文说明》第五节一致, 也是课件反复强调的):
    **权限只在服务端判定**, 前端隐藏菜单/按钮只是体验优化。
    所以每个需要权限的接口都挂 require_permission("xxx"), 而不是信任前端传来的角色。

缓存:
    每个请求都连表查权限太浪费, 结果缓存在 Redis 里。
    缓存的 key 带一个全局版本号, 任何角色/权限变更只把版本号 +1,
    旧缓存整体失效, 不需要扫描删除。
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.core.exceptions import ForbiddenError
from app.core.store import get_store
from app.models.rbac import Permission, RolePermission, UserRole
from app.models.user import User

PERM_VERSION_KEY = "rbac:perm:version"


def invalidate_permission_cache() -> None:
    """角色/权限变更后调用: 全局版本号自增, 已有缓存自然失效。"""
    get_store().incr(PERM_VERSION_KEY)


def _cache_version() -> str:
    return get_store().get(PERM_VERSION_KEY) or "0"


def user_role_ids(user: User) -> set[int]:
    return {role.role_id for role in user.roles}


def user_role_names(user: User) -> list[str]:
    return [role.role_name for role in user.roles]


def is_super_admin(user: User) -> bool:
    """系统管理员角色直接放行全部权限(禅道里管理员组也是这个语义)。"""
    return bool(user_role_ids(user) & settings.admin_role_ids)


def user_permission_keys(db: Session, user: User) -> set[str]:
    """查询用户拥有的全部 perm_key。"""
    key = f"rbac:perm:{_cache_version()}:user:{user.id}"
    store = get_store()
    cached = store.get(key)
    if cached is not None:
        try:
            return set(json.loads(cached))
        except json.JSONDecodeError:
            pass

    stmt = (
        select(Permission.perm_key)
        .join(RolePermission, RolePermission.perm_id == Permission.perm_id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(UserRole.user_id == user.id)
        .distinct()
    )
    keys = set(db.execute(stmt).scalars().all())

    store.set(key, json.dumps(sorted(keys)), ttl=settings.RBAC_CACHE_TTL)
    return keys


def has_permission(db: Session, user: User, perm_key: str) -> bool:
    if is_super_admin(user):
        return True
    return perm_key in user_permission_keys(db, user)


def require_permission(perm_key: str):
    """生成一个权限依赖: Depends(require_permission("role:manage"))。

    校验失败抛 403, 由统一异常处理器转成 {code, message, data}。
    """

    def checker(user: CurrentUser, db: DbSession) -> User:
        if not has_permission(db, user, perm_key):
            raise ForbiddenError(f"没有权限执行该操作(缺少 {perm_key})")
        return user

    return checker
