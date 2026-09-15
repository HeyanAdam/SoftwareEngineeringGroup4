"""pytest 全局夹具: SQLite(aiosqlite) + fakeredis, 完全不依赖 MySQL / Redis / MinIO。

要点
----
1. `app.core.database.engine` 在 import 时就按 `settings.DATABASE_URL` 创建,
   所以环境变量必须在 import app.* 之前设置好 (下面的 env 段)。
2. 测试用 SQLite 文件库, 并把 engine 换成 NullPool: pytest-asyncio 每个用例
   一个新事件循环, 连接池跨循环复用会炸。
3. Redis 用 fakeredis 替换 `app.core.redis.Redis` / `get_pool` —— 所有模块都是
   `from app.core.redis import get_redis` 拿函数对象, 函数内部再解析模块级 `Redis`,
   因此只打这两个补丁就能覆盖 auth / cache / rate_limit / ws manager / dashboard。
4. MinIO 相关调用在 health / main 里被 monkeypatch 掉, 不会真连 9000 端口。
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 1) 环境变量 (必须早于任何 app.* 导入)
# ---------------------------------------------------------------------------
API_DIR = Path(__file__).resolve().parents[1]


def _pick_work_dir() -> Path:
    """挑一个真正可写的临时目录 (受限/沙箱环境里 mkdtemp 可能不可用)。"""
    candidates: list[Path] = []
    override = os.environ.get("SG4_TEST_TMPDIR")
    if override:
        candidates.append(Path(override))
    candidates.append(Path(tempfile.gettempdir()) / "sg4-api-tests")
    candidates.append(API_DIR / ".pytest-tmp")

    errors: list[str] = []
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True, mode=0o777)
            probe = candidate / ".write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:  # pragma: no cover - 环境相关
            errors.append(f"{candidate}: {exc}")
            continue
        return candidate
    raise RuntimeError("找不到可写临时目录, 请设置 SG4_TEST_TMPDIR; 已尝试: " + "; ".join(errors))


WORK_DIR = _pick_work_dir()
DB_FILE = WORK_DIR / "sg4-tests.sqlite3"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{DB_FILE.as_posix()}"

os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SECRET_KEY"] = "test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["SEED_DEMO_DATA"] = "false"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/15"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["MINIO_ENDPOINT"] = "127.0.0.1:9000"

# ---------------------------------------------------------------------------
# 2) 应用导入 (环境变量已就绪)
# ---------------------------------------------------------------------------
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app import main as main_module  # noqa: E402
from app.api.v1 import health as health_module  # noqa: E402
from app.core import database  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models.chat import ChatMessage, ChatRoom  # noqa: E402
from app.models.rbac import Permission, Role  # noqa: E402
from app.models.stats import DailyStat  # noqa: E402
from app.models.user import User  # noqa: E402

# 所有测试账号共用同一个密码 (bcrypt rounds=12, 只算一次)
TEST_PASSWORD = "Passw0rd!23"

PERMISSION_SPECS: list[tuple[str, str, str]] = [
    ("users:read", "查看用户", "users"),
    ("users:write", "维护用户", "users"),
    ("roles:read", "查看角色", "roles"),
    ("roles:write", "维护角色权限", "roles"),
    ("files:read", "查看文件", "files"),
    ("dashboard:read", "查看仪表盘", "dashboard"),
    ("chat:read", "查看聊天", "chat"),
    ("chat:write", "发送消息", "chat"),
]

ROLE_SPECS: list[tuple[str, str, str]] = [
    ("super_admin", "超级管理员", "*"),
    (
        "admin",
        "管理员",
        "users:read,users:write,roles:read,roles:write,"
        "files:read,dashboard:read,chat:read,chat:write",
    ),
    ("viewer", "访客", "dashboard:read,chat:read,chat:write"),
]

# username, email, is_superuser, roles
USER_SPECS: list[tuple[str, str, bool, list[str]]] = [
    ("root", "root@example.com", True, ["super_admin"]),
    ("admin1", "admin1@example.com", False, ["admin"]),
    ("viewer1", "viewer1@example.com", False, ["viewer"]),
]

DEFAULT_ROOM = "lobby"

# ---------------------------------------------------------------------------
# 3) 断言测试配置生效 (否则说明 import 顺序被破坏)
# ---------------------------------------------------------------------------
assert settings.DATABASE_URL == TEST_DATABASE_URL, "DATABASE_URL 未被子进程环境覆盖"
assert settings.APP_ENV == "test"
assert settings.SEED_DEMO_DATA is False

# NullPool: 规避 pytest-asyncio 每用例新事件循环导致的连接跨循环复用
database.engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
database.AsyncSessionLocal.configure(bind=database.engine)

SEEDED: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# 4) fake redis
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def fake_redis() -> Iterator[Any]:
    """把 `app.core.redis` 的客户端工厂换成共享 FakeServer 的 fakeredis。"""
    import fakeredis

    from app.core import redis as redis_module

    fake_cls = getattr(fakeredis.aioredis, "FakeRedis", None) or fakeredis.aioredis.FakeAsyncRedis
    server = fakeredis.FakeServer()
    original_redis, original_pool = redis_module.Redis, redis_module.get_pool

    def _fake_redis(*_args: Any, **_kwargs: Any) -> Any:
        # 每次调用返回新客户端 (共享同一 server), 避免某个调用方 aclose() 影响别人
        return fake_cls(server=server, decode_responses=True)

    redis_module.Redis = _fake_redis
    redis_module.get_pool = lambda: None
    try:
        yield server
    finally:
        redis_module.Redis = original_redis
        redis_module.get_pool = original_pool


@pytest.fixture(autouse=True)
def patch_external_services(monkeypatch: pytest.MonkeyPatch) -> None:
    """MinIO / Redis 探活 / Pub-Sub 监听器全部短路, 保证测试离线且快速。"""

    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def _ok(*_args: Any, **_kwargs: Any) -> bool:
        return True

    async def _idle_listener(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(health_module, "ensure_bucket", _noop)
    monkeypatch.setattr(health_module, "redis_ping", _ok)
    monkeypatch.setattr(main_module, "ensure_bucket", _noop)
    monkeypatch.setattr(main_module, "redis_ping", _ok)
    monkeypatch.setattr(main_module, "pubsub_listener", _idle_listener)


# ---------------------------------------------------------------------------
# 5) 数据库建表 + 种子数据 (session 级, 用独立事件循环跑, 与用例循环解耦)
# ---------------------------------------------------------------------------
async def _create_schema() -> None:
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _seed() -> dict[str, Any]:
    async with database.AsyncSessionLocal() as db:
        permissions: dict[str, Permission] = {}
        for index, (code, name, module) in enumerate(PERMISSION_SPECS):
            permission = Permission(code=code, name=name, module=module, sort=index)
            db.add(permission)
            permissions[code] = permission
        await db.flush()

        roles: dict[str, Role] = {}
        for code, name, perm_expr in ROLE_SPECS:
            codes = (
                list(permissions) if perm_expr == "*" else [c for c in perm_expr.split(",") if c]
            )
            role = Role(code=code, name=name, description=f"{name} (tests)", is_builtin=True)
            role.permissions = [permissions[c] for c in codes]
            db.add(role)
            roles[code] = role
        await db.flush()

        hashed = hash_password(TEST_PASSWORD)
        users: dict[str, User] = {}
        for username, email, is_superuser, role_codes in USER_SPECS:
            user = User(
                username=username,
                email=email,
                full_name=username.title(),
                hashed_password=hashed,
                is_active=True,
                is_superuser=is_superuser,
            )
            user.roles = [roles[c] for c in role_codes]
            db.add(user)
            users[username] = user
        await db.flush()

        room = ChatRoom(code=DEFAULT_ROOM, name="公共大厅", description="tests", is_default=True)
        db.add(room)
        await db.flush()
        db.add_all(
            [
                ChatMessage(
                    room_id=room.id,
                    sender_id=None,
                    sender_name="seed",
                    kind="system",
                    content="seeded message 1",
                ),
                ChatMessage(
                    room_id=room.id,
                    sender_id=users["root"].id,
                    sender_name="root",
                    kind="text",
                    content="seeded message 2",
                ),
            ]
        )

        today: date = datetime.now(UTC).date()
        for offset in range(30):
            db.add(
                DailyStat(
                    stat_date=today - timedelta(days=offset),
                    metric="active_users",
                    value=50 + offset,
                    dimension="all",
                )
            )
        for name, weight in (("前端开发", 30), ("后端开发", 25), ("测试与联调", 18)):
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

        return {
            "users": {name: user.id for name, user in users.items()},
            "roles": {code: role.id for code, role in roles.items()},
            "permissions": {code: perm.id for code, perm in permissions.items()},
            "room": room.id,
        }


@pytest.fixture(scope="session", autouse=True)
def prepared_database() -> Iterator[dict[str, Any]]:
    DB_FILE.unlink(missing_ok=True)
    asyncio.run(_create_schema())
    SEEDED.update(asyncio.run(_seed()))
    try:
        yield SEEDED
    finally:
        asyncio.run(database.engine.dispose())
        DB_FILE.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def seeded(prepared_database: dict[str, Any]) -> dict[str, Any]:
    """种子数据的 id 映射: {"users": {...}, "roles": {...}, "permissions": {...}, "room": id}。"""
    return prepared_database


# ---------------------------------------------------------------------------
# 6) HTTP / 依赖覆盖
# ---------------------------------------------------------------------------
async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with database.AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(scope="session", autouse=True)
def override_get_db_dependency() -> Iterator[None]:
    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def client(seeded: dict[str, Any]) -> AsyncGenerator[AsyncClient, None]:
    """不跑 lifespan 的 ASGI 客户端 (lifespan 里的 MinIO/Redis 初始化与测试无关)。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.fixture
def api_prefix() -> str:
    return settings.API_V1_PREFIX


@pytest.fixture(scope="session")
def test_password() -> str:
    """种子账号统一密码 (供同步 TestClient 用)。"""
    return TEST_PASSWORD


@pytest.fixture
def login(client: AsyncClient):
    """异步登录助手: 返回 token 字典 (access_token / refresh_token / ...)。"""

    async def _login(username: str, password: str = TEST_PASSWORD) -> dict[str, Any]:
        response = await client.post(
            f"{settings.API_V1_PREFIX}/auth/login",
            json={"username": username, "password": password},
        )
        assert response.status_code == 200, response.text
        return response.json()

    return _login


@pytest.fixture
def bearer():
    def _bearer(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _bearer
