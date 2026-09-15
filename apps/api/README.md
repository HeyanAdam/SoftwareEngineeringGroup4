# SG4 API · 后端服务

FastAPI 后端: 认证/RBAC、用户与角色管理、文件对象存储、仪表盘聚合、WebSocket 实时通信。

完整说明见仓库根目录 [README.md](../../README.md) 与 [docs/](../../docs/)。

## 本机开发

```bash
# 1. 起依赖 (仓库根目录)
pnpm up:infra

# 2. 安装依赖 (本目录)
python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

# 3. 迁移 + 种子数据
alembic upgrade head
python -m app.initial_data

# 4. 启动
uvicorn app.main:app --reload --port 8000
```

- Swagger: http://127.0.0.1:8000/api/v1/docs
- 健康检查: http://127.0.0.1:8000/api/v1/health/ready

## 目录职责

```text
app/
├── main.py          应用装配 (中间件 / 路由 / lifespan)
├── initial_data.py  权限点、内置角色、演示数据 (幂等, 可反复执行)
├── core/            配置、数据库、Redis、MinIO、安全、日志、异常、限流、分页
├── models/          SQLAlchemy 2.0 ORM
├── schemas/         Pydantic v2 出入参 (含 WebSocket 消息协议)
├── services/        业务逻辑 (auth/user/file/dashboard/chat)
├── api/v1/          路由层: 参数校验 + 调用 service, 不写 SQL
└── ws/              WebSocket 连接管理与端点
```

约定: 路由层不写 SQL; service 层不依赖 FastAPI 对象; 所有业务失败抛 `app.core.exceptions` 中的异常类。

## 常用命令

```bash
pytest -q                                       # 测试 (无需外部服务)
ruff check app tests && ruff format app tests   # 规范与格式化
mypy app                                        # 类型检查
alembic revision --autogenerate -m "add xxx"    # 生成迁移
alembic upgrade head / downgrade -1             # 升级 / 回滚
```

## 新增一个业务模块

1. `app/models/xxx.py` 定义模型, 并在 `app/models/__init__.py` 导出 (alembic 自动发现依赖它)
2. `alembic revision --autogenerate -m "add xxx"`
3. `app/schemas/xxx.py` 定义出入参
4. `app/services/xxx.py` 写业务逻辑
5. `app/api/v1/xxx.py` 写路由, 在 `app/api/v1/__init__.py` 注册
6. 需要新权限点时, 在 `app/initial_data.py` 的 `PERMISSIONS` 增加并挂到角色上
