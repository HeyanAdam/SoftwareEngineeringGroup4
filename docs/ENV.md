# 环境变量说明

所有配置项集中在仓库根目录 **`.env`** (由 `docker compose` 注入容器) 与 **`apps/api/.env`** (本机裸跑后端时使用)。

- 模板: `.env.example` / `apps/api/.env.example`
- 变量名大小写不敏感, 后端通过 `app/core/config.py` (pydantic-settings) 读取
- **新增配置项时必须同时更新 `.env.example` 与本文档**

## 1. 项目与端口

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `COMPOSE_PROJECT_NAME` | `sg4` | Compose 项目名, 决定容器/网络/卷前缀 |
| `TZ` | `Asia/Shanghai` | 容器时区 |
| `WEB_PORT` | `8080` | 前端宿主机端口 → 容器 80 |
| `WEB_DEV_PORT` | `5173` | 仅 dev profile: 容器化 Vite 开发服务器端口 |
| `API_PORT` | `8000` | 后端宿主机端口 → 容器 8000 |
| `MYSQL_PORT` | `3306` | MySQL 宿主机端口 |
| `REDIS_PORT` | `6379` | Redis 宿主机端口 |
| `MINIO_API_PORT` | `9000` | MinIO S3 API 端口 |
| `MINIO_CONSOLE_PORT` | `9001` | MinIO 控制台端口 |

## 2. 依赖服务

| 变量 | 说明 |
| --- | --- |
| `MYSQL_ROOT_PASSWORD` | MySQL root 口令 (仅容器初始化用) |
| `MYSQL_DATABASE` | 业务库名, 默认 `sg4` |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 应用账号口令 |
| `REDIS_PASSWORD` | Redis 访问口令 |
| `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` | MinIO 管理员账号 |
| `MINIO_BUCKET` | 默认文件桶, 首次启动自动创建 |

## 3. 后端应用

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | `local`/`development`/`staging`/`production`/`test`; 生产会校验 `SECRET_KEY` 强度并关闭 `/docs` |
| `DEBUG` | `true` | 调试开关 |
| `LOG_LEVEL` | `INFO` | 日志级别, 生产建议 `INFO`, 排查时 `DEBUG` |
| `DATABASE_URL` | `mysql+aiomysql://...` | SQLAlchemy 异步 URL。**容器内 host 必须是 `mysql`**, 本机裸跑用 `127.0.0.1` |
| `DB_ECHO` | `false` | 打印 SQL, 排查慢查询时临时开启 |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_RECYCLE` | `10/20/1800` | 连接池参数; 多副本部署时注意 MySQL `max_connections` |
| `REDIS_URL` | `redis://:<pwd>@redis:6379/0` | 含口令时立刻生效, 格式 `redis://:password@host:port/db` |
| `REDIS_MAX_CONNECTIONS` | `50` | 连接池上限 |
| `CACHE_TTL_SECONDS` | `60` | 默认缓存过期时间 |
| `MINIO_ENDPOINT` | `minio:9000` | 服务端访问地址 (容器内) |
| `MINIO_PUBLIC_ENDPOINT` | `127.0.0.1:9000` | **浏览器可达**地址, 预签名 URL 用它生成; 生产填对外域名 |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | — | 与 `MINIO_ROOT_USER/PASSWORD` 对应 |
| `MINIO_BUCKET` | `sg4-files` | 目标桶 |
| `MINIO_SECURE` | `false` | 是否为 HTTPS |
| `MINIO_PRESIGN_EXPIRE` | `3600` | 下载链接有效期(秒) |
| `MAX_UPLOAD_SIZE_MB` | `50` | 单文件上限 |
| `ALLOWED_UPLOAD_TYPES` | 见 `.env.example` | MIME 白名单, 逗号分隔; 留空表示不限制 |
| `SECRET_KEY` | — | JWT 签名密钥。**必须修改**, 生成: `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | `HS256` | 签名算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | access 有效期 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | refresh 有效期 |
| `PASSWORD_MIN_LENGTH` | `8` | 注册密码最小长度 |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCK_SECONDS` | `10` / `300` | 登录失败锁定策略 |
| `CORS_ORIGINS` | `http://localhost:5173,...` | 逗号分隔白名单; 同源部署(nginx 反代)时可留空 |
| `WS_PATH` | `/ws` | WebSocket 路径 |
| `WS_HEARTBEAT_SECONDS` | `25` | 心跳间隔; 空闲超时 = 2 倍 |
| `WS_MAX_MESSAGE_BYTES` | `65536` | 单条 WS 消息上限 |
| `RATE_LIMIT_PER_MINUTE` | `600` | 全局每 IP 每分钟请求上限 |
| `AUTO_CREATE_TABLES` | `1` | 启动时按 ORM 建表 (仅开发便利); 生产设 `0`, 用 alembic |
| `SEED_DEMO_DATA` | `1` | 写入演示账号/统计; **生产设 `0`** |
| `ENABLE_DOCS` | `true` | 是否暴露 `/api/v1/docs`; 生产自动关闭 |
| `RUN_MIGRATIONS` | `1` | 容器启动时执行 `alembic upgrade head` |
| `UVICORN_WORKERS` | `1` | uvicorn 进程数。注意: 每进程独立持有 WS 连接, 广播靠 Redis Pub/Sub 保证跨进程可达 |
| `APP_VERSION` / `GIT_SHA` | `0.1.0` / `dev` | 由 CI 注入, 用于 `/health/info` 定位版本 |

## 4. 前端 (构建期变量, 必须 `VITE_` 前缀)

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` | REST 前缀; 开发时由 Vite 代理到 `127.0.0.1:8000` |
| `VITE_WS_BASE_URL` | `/ws` | WebSocket 路径, 前端自动拼 `ws://`/`wss://` 与 `token` 参数 |
| `VITE_APP_TITLE` | `SG4 管理台` | 页面标题 / 浏览器标签 |
| `VITE_PORT` | `5173` | 开发服务器端口 |

> Vite 变量在**构建时**内联, 修改后需重新构建镜像 (`pnpm up --build` 或 `docker compose build web`)。

## 5. 关于 `.env` 的安全要求

- `.env` 已被 `.gitignore` 忽略, **绝不提交**。
- 生产密钥建议由 Secrets Manager / CI Secret 注入, 不要写进镜像或 compose 文件。
- CI 里已启用 gitleaks 扫描; 一旦误提交密钥, 立即轮换并清理 git 历史。
