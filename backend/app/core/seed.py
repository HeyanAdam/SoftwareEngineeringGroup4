"""初始化数据: 内置角色、16 条权限、管理员账号。

幂等: 每次启动都会执行, 已存在的数据一律跳过, 不会覆盖你在后台改过的授权结果。

权限标识说明:
    《权限表》只规定了 perm_key 的格式(模块:操作, 示例 studyplan:add、school:manage)
    以及 module_name 的 7 个取值范围, 没有逐条列出具体权限。
    下面 16 条是按这 7 个模块 + 项目现有功能生成的**初始种子数据**,
    落库后可在「角色管理」页勾选调整, 不属于脱离权限表。
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.account import UserAccount
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User

logger = logging.getLogger("kaoyan.seed")

# ---------------- 角色(权限表 role_name 字典里的两个初始值) ----------------
ROLE_SEEDS: list[tuple[int, str, str]] = [
    (1, "考研学生", "使用择校、刷题、模考、复试训练、督学陪伴与资讯功能"),
    (2, "系统管理员", "维护用户、角色与权限, 拥有全部功能权限"),
]

# ---------------- 权限(7 个模块, 16 条) ----------------
PERMISSION_SEEDS: list[tuple[str, str, str]] = [
    ("school:view", "查看院校信息", "择校模块"),
    ("school:manage", "维护院校数据", "择校模块"),
    ("question:practice", "刷题练习", "刷题训练模块"),
    ("question:manage", "维护题库", "刷题训练模块"),
    ("exam:take", "参加模考", "模考测评模块"),
    ("exam:manage", "维护试卷与成绩", "模考测评模块"),
    ("interview:practice", "复试模拟训练", "复试训练模块"),
    ("interview:manage", "维护复试题库", "复试训练模块"),
    ("studyplan:view", "查看学习计划", "督学陪伴模块"),
    ("studyplan:add", "新建学习计划", "督学陪伴模块"),
    ("studyplan:manage", "管理全部学习计划", "督学陪伴模块"),
    ("news:view", "浏览资讯政策", "资讯政策模块"),
    ("news:manage", "维护资讯内容", "资讯政策模块"),
    ("user:manage", "用户与账号管理", "后台管理模块"),
    ("role:manage", "角色与权限配置", "后台管理模块"),
    ("perm:view", "查看权限清单", "后台管理模块"),
]

STUDENT_PERMISSION_KEYS: list[str] = [
    "school:view",
    "question:practice",
    "exam:take",
    "interview:practice",
    "studyplan:view",
    "studyplan:add",
    "news:view",
]


def _seed_roles(db: Session) -> dict[str, Role]:
    roles: dict[str, Role] = {}
    for role_id, name, desc in ROLE_SEEDS:
        role = db.scalar(select(Role).where(Role.role_name == name))
        if role is None:
            role = Role(role_id=role_id, role_name=name, role_desc=desc)
            db.add(role)
            db.flush()
            logger.info("初始化角色: %s", name)
        roles[name] = role
    return roles


def _seed_permissions(db: Session) -> dict[str, Permission]:
    perms: dict[str, Permission] = {}
    for perm_key, perm_name, module_name in PERMISSION_SEEDS:
        perm = db.scalar(select(Permission).where(Permission.perm_key == perm_key))
        if perm is None:
            perm = Permission(
                perm_key=perm_key, perm_name=perm_name, module_name=module_name
            )
            db.add(perm)
            db.flush()
        perms[perm_key] = perm
    return perms


def _grant(db: Session, role: Role, permissions: list[Permission]) -> int:
    """给角色补授权限, 已授权的跳过。"""
    existing = {
        row.perm_id
        for row in db.scalars(
            select(RolePermission).where(RolePermission.role_id == role.role_id)
        )
    }
    added = 0
    for perm in permissions:
        if perm.perm_id in existing:
            continue
        db.add(RolePermission(role_id=role.role_id, perm_id=perm.perm_id))
        added += 1
    return added


def _seed_admin_user(db: Session, admin_role: Role) -> None:
    """首次启动创建管理员账号(已存在则跳过, 不改密码)。"""
    exists = db.scalar(select(User).where(User.username == settings.ADMIN_LOGIN_NAME))
    if exists is not None:
        return

    admin = User(
        username=settings.ADMIN_LOGIN_NAME,
        email=settings.ADMIN_EMAIL,
        password_hash=hash_password(settings.ADMIN_INITIAL_PASSWORD),
        account_status=1,
    )
    db.add(admin)
    db.flush()
    db.add(UserAccount(user_id=admin.id, user_name="系统管理员"))
    db.add(UserRole(user_id=admin.id, role_id=admin_role.role_id))
    logger.warning(
        "已创建初始管理员: 登录名=%s 密码=%s (请登录后立即修改)",
        settings.ADMIN_LOGIN_NAME,
        settings.ADMIN_INITIAL_PASSWORD,
    )


def seed_rbac(db: Session) -> dict[str, int]:
    """写入初始角色、权限、授权关系与管理员账号。"""
    roles = _seed_roles(db)
    perms = _seed_permissions(db)

    student = roles["考研学生"]
    admin = roles["系统管理员"]

    student_added = _grant(
        db,
        student,
        [perms[key] for key in STUDENT_PERMISSION_KEYS if key in perms],
    )
    admin_added = _grant(db, admin, list(perms.values()))
    _seed_admin_user(db, admin)

    db.commit()

    if student_added or admin_added:
        logger.info(
            "授权初始化: 考研学生 +%d 条, 系统管理员 +%d 条", student_added, admin_added
        )
    return {
        "roles": db.scalar(select(func.count()).select_from(Role)) or 0,
        "permissions": db.scalar(select(func.count()).select_from(Permission)) or 0,
        "student_permissions": student_added,
        "admin_permissions": admin_added,
    }
