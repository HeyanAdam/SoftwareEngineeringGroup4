# 考研 AI 导学平台 · 后端

基于 FastAPI 的后端服务，采用「模块化单体」结构：一个进程、一套数据库，业务按模块分目录，便于多人并行开发。

> **当前阶段：脚手架已就绪。** 分层约定与基础设施（配置、数据库、鉴权、异常）已定型；
> `user` / `ai_chat` / `study_plan` 三个模块是**参考示例**，演示「一张表 + 一组接口」该怎么写。
> 新增自己的模块请照 **[../docs/SCAFFOLD.md](../docs/SCAFFOLD.md)** 第 4 节的六步来。

## 技术栈

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.0（MySQL）
- Redis（缓存 / 会话）
- MinIO（多模态文件）
- PyJWT + argon2（登录鉴权）

## 目录结构

```text
kaoyan-backend/
├── app/
│   ├── main.py                 入口：创建 FastAPI、配置 CORS、注册各模块路由
│   ├── core/                   与业务无关的基础设施
│   │   ├── config.py           读取 .env 的配置对象 settings
│   │   ├── database.py         SQLAlchemy 引擎、SessionLocal、get_db 依赖、Base
│   │   ├── security.py         密码哈希、JWT 签发与校验
│   │   └── deps.py             依赖注入：get_current_user（当前登录用户）
│   ├── models/                 ORM 模型（数据库表）集中在此
│   │   ├── user.py             User
│   │   ├── chat.py             ChatSession / ChatMessage
│   │   └── plan.py             StudyPlan / PlanTask
│   ├── schemas/                请求与响应模型（Pydantic），与前端契约一致
│   └── modules/                业务模块，每个模块自带 router
│       ├── user/
│       │   ├── router.py       注册 / 登录 / 个人信息
│       │   └── service.py      业务逻辑
│       ├── ai_chat/
│       │   ├── router.py       会话管理 / 消息收发
│       │   └── service.py      问答逻辑（当前为规则式回答，后续接入 RAG）
│       └── study_plan/
│           ├── router.py       计划与任务 CRUD / 进度
│           └── service.py      计划生成逻辑
├── requirements.txt
├── .env.example
└── README.md
```

**分层约定**

| 层 | 职责 | 不要做的事 |
| --- | --- | --- |
| `modules/*/router.py` | 定义路径、参数校验、调用 service | 不写 SQL、不写复杂业务分支 |
| `modules/*/service.py` | 业务逻辑、事务 | 不直接依赖 FastAPI 的 Request/Response |
| `models/` | 表结构 | 不放业务逻辑 |
| `schemas/` | 出入参结构 | 不放数据库操作 |
| `core/` | 配置、连接、鉴权等基础设施 | 不依赖任何业务模块 |

## 启动方式

```bash
# 1. 启动依赖服务（在仓库根目录执行）
docker compose up -d

# 2. 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate            # macOS / Linux: source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 复制配置（默认值已与 docker-compose 对齐，无需修改）
copy .env.example .env

# 5. 启动服务
uvicorn app.main:app --reload --port 8001
```

- Swagger UI：http://127.0.0.1:8001/docs
- ReDoc：http://127.0.0.1:8001/redoc

依赖的数据库服务：MySQL（宿主机端口 **3307**）、Redis（6379）、MinIO（9000 / 9001）。

## 环境变量

见 `.env.example`，常用项：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_HOST` / `DB_PORT` | `localhost` / `3307` | MySQL 地址。**端口是 3307**，compose 映射所致 |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `root` / `kaoyan123` / `kaoyan` | 与 `docker-compose.yml` 一致 |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | Redis |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO API |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` / `minioadmin` | MinIO 账号 |
| `BACKEND_PORT` | `8001` | 后端端口 |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 允许跨域的前端地址 |
| `SECRET_KEY` | 需替换 | JWT 签名密钥，生产环境务必改为随机值 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 登录有效期（分钟） |

## 接口一览

> 下面三个模块都是**参考示例**，用来演示接口写法与分层方式；最终接口以需求评审结果为准。
> 以 http://127.0.0.1:8001/docs 为最终依据。前端调用统一走 `/api/...`，由 Vite 代理转发到 8001。

| 模块 | 路径 | 说明 |
| --- | --- | --- |
| 系统 | `GET /` | 启动确认 |
| 系统 | `GET /api/db-check` | 数据库连接测试（返回 MySQL 版本） |
| 用户 🟡 | `POST /api/user/register` | 注册（用户名 / 邮箱 / 密码） |
| 用户 🟡 | `POST /api/user/login` | 登录，返回 access_token |
| 用户 🟡 | `GET /api/user/me` | 当前登录用户信息（需 token） |
| 用户 🟡 | `PUT /api/user/me` | 修改昵称 / 目标院校专业等资料（需 token） |
| AI 对话 🟡 | `GET /api/ai/sessions` | 我的会话列表（需 token） |
| AI 对话 🟡 | `POST /api/ai/sessions` | 新建会话（需 token） |
| AI 对话 🟡 | `DELETE /api/ai/sessions/{id}` | 删除会话（需 token） |
| AI 对话 🟡 | `GET /api/ai/sessions/{id}/messages` | 会话消息历史（需 token） |
| AI 对话 🟡 | `POST /api/ai/sessions/{id}/messages` | 发送消息并获取回答（需 token，回答目前是关键词规则） |
| 学习规划 🟡 | `GET /api/plan/plans` | 我的学习计划（需 token） |
| 学习规划 🟡 | `POST /api/plan/plans` | 创建计划（自动生成阶段任务，需 token） |
| 学习规划 🟡 | `GET /api/plan/plans/{id}` | 计划详情含任务列表（需 token） |
| 学习规划 🟡 | `PATCH /api/plan/plans/{id}` | 修改计划（需 token） |
| 学习规划 🟡 | `DELETE /api/plan/plans/{id}` | 删除计划（需 token） |
| 学习规划 🟡 | `PATCH /api/plan/tasks/{id}` | 更新任务状态 / 备注（需 token） |
| 学习规划 🟡 | `GET /api/plan/stats` | 计划完成情况统计（需 token） |

## 数据库表

| 表 | 说明 |
| --- | --- |
| `users` | 用户账号与画像字段（昵称、目标院校、目标专业、考试年份） |
| `chat_sessions` | AI 对话会话 |
| `chat_messages` | 会话内的消息（user / assistant） |
| `study_plans` | 学习计划（科目、起止日期、每日时长） |
| `plan_tasks` | 计划下的阶段任务与完成状态 |

开发阶段由 `Base.metadata.create_all()` 在启动时自动建表（见 `app/core/database.py`）。表结构稳定后改用 Alembic 迁移。

## 添加新模块的步骤

1. 在 `app/modules/` 下新建目录，例如 `recommend/`
2. 建 `__init__.py`、`router.py`（必要时加 `service.py`）
3. 在 `router.py` 里用 `APIRouter(prefix="/api/recommend", tags=["推荐模块"])` 定义接口
4. 在 `app/main.py` 里 `app.include_router(recommend_router)` 注册
5. 需要新表时，在 `app/models/` 加模型并在 `app/models/__init__.py` 导入，重启即自动建表

## 常见问题

| 问题 | 处理 |
| --- | --- |
| `uvicorn` 不是内部或外部命令 | 虚拟环境没激活：`venv\Scripts\activate` |
| 连不上 MySQL | 确认 `docker ps` 里 `kaoyan-mysql` 在运行，且 `.env` 的 `DB_PORT=3307` |
| 表不存在 / 字段报错 | 删掉旧表重启（开发期），或检查 `app/models/__init__.py` 是否导入了新模型 |
| 接口返回 401 | 请求头缺少 `Authorization: Bearer <token>`，或 token 已过期（默认 24 小时） |
| Redis / MinIO 连不上 | 后端不强依赖它们即可启动；用到对应功能时再启动容器 |
