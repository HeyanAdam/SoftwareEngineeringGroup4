# 测试套件

无需 MySQL / Redis / MinIO, 全部依赖在进程内替身:

| 真实依赖 | 测试替身 |
| --- | --- |
| MySQL | `sqlite+aiosqlite` 临时文件库 (`NullPool`, 规避 pytest-asyncio 每个用例新事件循环) |
| Redis | `fakeredis.aioredis.FakeRedis` (共享 `FakeServer`), 替换 `app.core.redis.Redis` / `get_pool` |
| MinIO | `health.ensure_bucket` / `main.ensure_bucket` 被 monkeypatch 成空操作 |

```bash
.venv\Scripts\python -m pytest            # 全量 (Windows)
.venv\Scripts\python -m pytest tests/test_auth.py -q
.venv\Scripts\python -m pytest -k websocket -q
.venv\Scripts\pytest --cov=app --cov-report=term-missing     # CI 用法
```

## 实现要点 (conftest.py)

1. **环境变量必须先于 `import app.*`**: `app.core.database` 在 import 期就按
   `settings.DATABASE_URL` 创建 engine。conftest 顶部先写
   `DATABASE_URL=sqlite+aiosqlite:///<tmp>/sg4-tests.sqlite3`、`APP_ENV=test`、
   `SECRET_KEY=...`、`AUTO_CREATE_TABLES=true`、`SEED_DEMO_DATA=false`,
   并断言 `settings.DATABASE_URL` 确实被覆盖。
2. **engine 换成 NullPool**: `database.AsyncSessionLocal.configure(bind=...)`,
   这样 `ws/routes.py`、`health.py` 里 `from app.core.database import AsyncSessionLocal`
   的引用同样生效。
3. **Redis**: 只 patch `app.core.redis.Redis` 与 `get_pool` 两个模块级名字, 因为各模块
   都是 `from app.core.redis import get_redis` 拿函数对象, 函数内部才解析 `Redis`,
   因此 auth / 限流 / 缓存 / dashboard / WS 广播全部自动走 fakeredis。
4. **`get_db` 依赖覆盖** + 不跑 lifespan 的 `httpx.AsyncClient(ASGITransport(app))`。
5. **种子数据** session 级一次写入 (bcrypt 只算一次): 3 个角色 / 8 个权限点 /
   `root`(超管) `admin1` `viewer1` 三个账号 / `lobby` 聊天室与 2 条历史消息 /
   30 天 `active_users` 趋势 + `category` 维度数据。密码统一 `Passw0rd!23`。
6. 临时目录通过 `SG4_TEST_TMPDIR` 覆盖; 若默认临时目录不可写会自动降级到
   `apps/api/.pytest-tmp` (`_pick_work_dir()`), 受限沙箱里也能跑。

## 覆盖范围

| 文件 | 内容 |
| --- | --- |
| `test_health.py` | `/health/live`、`/health/ready`(依赖探针)、`/health/info`、`/metrics` |
| `test_auth.py` | 注册 + 登录 + `/auth/me`、刷新令牌旋转、登出使 refresh 失效、错误密码 401 信封、缺 token 401、422 校验信封、改密后 token_version 轮换 |
| `test_users_rbac.py` | 用户分页/关键字/详情/统计、低权限 403(带 code/message)、写接口需超管、非法分页 422、角色与权限点列表 |
| `test_dashboard.py` | `/dashboard/overview` 结构 (stats/trend/categories/role_distribution + extra)、缓存命中与 `cache/refresh`、未登录 401 |
| `test_chat.py` | 房间列表、历史消息(正序/limit/未知房间)、`/chat/online`; WebSocket `welcome -> chat -> ping/pong -> 非法消息 error` 往返; 非法 token 1008 关闭 |
| `test_migrations.py` | `alembic upgrade head --sql` 离线渲染 MySQL DDL, 与 ORM 元数据逐表逐列比对 (列名/类型/可空/`DEFAULT now()`/索引/唯一约束/外键 ondelete)、单 head 校验、downgrade 可生成 |

## 注意

* `test_migrations.py` 走的是**离线** MySQL 方言渲染 (与 CI 的
  `alembic upgrade head --sql` 同一条路径)。初始迁移面向 MySQL
  (`server_default=sa.text('now()')`), 不能直接对 SQLite 执行。
* WebSocket 用例是**同步** `TestClient` (`app.ws.manager.ConnectionManager`
  持有 `asyncio.Lock`, 跨事件循环复用会报错, 因此整个套件里只有它真正建立 WS 连接)。
* 环境变量 `SG4_TEST_TMPDIR` 可指定测试临时目录; 运行结束后 SQLite 文件会被删除。
