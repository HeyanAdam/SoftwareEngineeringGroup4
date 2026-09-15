"""初始化数据: 权限点 / 内置角色 / 管理员账号 / 聊天室 / 演示统计。

幂等设计, 可重复执行:
    python -m app.initial_data
容器启动脚本在 AUTO_CREATE_TABLES=1 时自动调用。
"""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_models
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.chat import ChatRoom
from app.models.rbac import Permission, Role
from app.models.stats import DailyStat
from app.models.user import User

logger = get_logger(__name__)

# code, name, module, sort
PERMISSIONS: list[tuple[str, str, str]] = [
    ("users:read", "查看用户", "users"),
    # 复合写权限: 授权后即可使用全部用户变更类接口
    ("users:write", "维护用户", "users"),
    ("users:create", "新建用户", "users"),
    ("users:update", "编辑用户", "users"),
    ("users:delete", "删除用户", "users"),
    ("users:assign-role", "分配角色", "users"),
    ("roles:read", "查看角色", "roles"),
    ("roles:write", "维护角色权限", "roles"),
    ("files:read", "查看文件", "files"),
    ("files:upload", "上传文件", "files"),
    ("files:download", "下载文件", "files"),
    ("files:delete", "删除文件", "files"),
    ("dashboard:read", "查看仪表盘", "dashboard"),
    ("chat:read", "查看聊天", "chat"),
    ("chat:write", "发送消息", "chat"),
    ("chat:broadcast", "全站广播", "chat"),
    ("system:monitor", "系统监控", "system"),
]

# code, name, description, 权限集合
ROLES: list[tuple[str, str, str, str]] = [
    ("super_admin", "超级管理员", "拥有全部权限, 不可删除", "*"),
    (
        "admin",
        "管理员",
        "用户/角色/文件管理 + 仪表盘, 不含系统监控",
        "users:read,users:write,users:create,users:update,users:delete,users:assign-role,"
        "roles:read,roles:write,"
        "files:read,files:upload,files:download,files:delete,"
        "dashboard:read,chat:read,chat:write,chat:broadcast",
    ),
    (
        "editor",
        "编辑",
        "内容与文件操作",
        "files:read,files:upload,files:download,dashboard:read,chat:read,chat:write",
    ),
    (
        "analyst",
        "分析师",
        "只读 + 仪表盘",
        "files:read,files:download,dashboard:read,chat:read",
    ),
    ("viewer", "访客", "默认角色, 仅基础浏览", "dashboard:read,chat:read,chat:write"),
]

DEMO_USERS: list[tuple[str, str, str, list[str]]] = [
    ("admin", "admin@example.com", "Admin@123456", ["super_admin"]),
    ("manager", "manager@example.com", "Manager@123456", ["admin"]),
    ("editor", "editor@example.com", "Editor@123456", ["editor"]),
    ("analyst", "analyst@example.com", "Analyst@123456", ["analyst"]),
    ("viewer", "viewer@example.com", "Viewer@123456", ["viewer"]),
]

DEMO_ROOMS: list[tuple[str, str, str, bool]] = [
    ("lobby", "公共大厅", "所有人可见的公共频道", True),
    ("dev", "研发频道", "研发进度与问题同步", False),
    ("ops", "运维频道", "部署与告警通知", False),
]


async def sync_permissions(db) -> dict[str, Permission]:  # noqa: ANN001
    existing = {p.code: p for p in (await db.execute(select(Permission))).scalars().all()}
    for index, (code, name, module) in enumerate(PERMISSIONS):
        row = existing.get(code)
        if row is None:
            row = Permission(code=code, name=name, module=module, sort=index)
            db.add(row)
            existing[code] = row
        else:
            row.name, row.module, row.sort = name, module, index
    await db.commit()
    logger.info("permissions_synced", count=len(PERMISSIONS))
    return existing


async def sync_roles(db, permissions: dict[str, Permission]) -> dict[str, Role]:  # noqa: ANN001
    existing = {r.code: r for r in (await db.execute(select(Role))).scalars().all()}
    desired: list[Role] = []
    for code, name, description, perm_expr in ROLES:
        role = existing.get(code)
        if role is None:
            role = Role(code=code, name=name, description=description, is_builtin=True)
            db.add(role)
            existing[code] = role
        else:
            role.name, role.description, role.is_builtin = name, description, True

        codes = (
            list(permissions)
            if perm_expr == "*"
            else [c.strip() for c in perm_expr.split(",") if c.strip()]
        )
        role.permissions = [permissions[c] for c in codes if c in permissions]
        desired.append(role)
    await db.commit()
    logger.info("roles_synced", count=len(desired))
    return existing


async def sync_demo_users(db, roles: dict[str, Role]) -> None:  # noqa: ANN001
    for username, email, password, role_codes in DEMO_USERS:
        user = (
            await db.execute(select(User).where(func.lower(User.username) == username))
        ).scalar_one_or_none()
        if user is not None:
            continue
        user = User(
            username=username,
            email=email,
            full_name=username.capitalize(),
            hashed_password=hash_password(password),
            is_active=True,
            is_superuser=username == "admin",
            remark="演示账号, 首次部署自动创建",
        )
        user.roles = [roles[c] for c in role_codes if c in roles]
        db.add(user)
        logger.info("demo_user_created", username=username, password=password)
    await db.commit()


async def sync_rooms(db) -> None:  # noqa: ANN001
    for code, name, description, is_default in DEMO_ROOMS:
        room = (
            await db.execute(select(ChatRoom).where(ChatRoom.code == code))
        ).scalar_one_or_none()
        if room is None:
            db.add(ChatRoom(code=code, name=name, description=description, is_default=is_default))
    await db.commit()


async def sync_daily_stats(db, days: int = 30) -> None:  # noqa: ANN001
    existing = (await db.execute(select(func.count()).select_from(DailyStat))).scalar_one()
    if existing:
        return

    today = datetime.now(UTC).date()
    rng = random.Random(20240501)  # 固定种子, 保证团队成员看到相同数据
    categories = [
        ("前端开发", 30),
        ("后端开发", 25),
        ("数据库设计", 12),
        ("测试与联调", 18),
        ("文档撰写", 9),
    ]
    for offset in range(days, -1, -1):
        stat_date: date = today - timedelta(days=offset)
        wave = days - offset
        base_users = 40 + int(wave * 1.6) + rng.randint(-6, 8)
        db.add(DailyStat(stat_date=stat_date, metric="active_users", value=max(base_users, 5)))
        db.add(
            DailyStat(
                stat_date=stat_date,
                metric="api_calls",
                value=max(base_users * rng.randint(30, 90), 100),
            )
        )
        db.add(DailyStat(stat_date=stat_date, metric="uploads", value=rng.randint(3, 40)))

    for name, weight in categories:
        db.add(
            DailyStat(
                stat_date=today,
                metric=name,
                value=weight,
                dimension="category",
                sort=weight,
            )
        )
    await db.commit()
    logger.info("daily_stats_seeded", days=days)


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        permissions = await sync_permissions(db)
        roles = await sync_roles(db, permissions)
        await sync_demo_users(db, roles)
        await sync_rooms(db)
        await sync_daily_stats(db)

    if settings.SEED_DEMO_DATA:
        logger.warning(
            "demo_data_ready",
            hint="默认账号 admin / Admin@123456 —— 生产环境请立刻修改或关闭 SEED_DEMO_DATA",
        )


async def main() -> None:
    await init_models()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
