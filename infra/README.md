# SG4 容器 / 基础设施层 (`infra/`)

本目录只包含**编排与运维**相关文件, 不含业务代码。业务后端在 `apps/api`, 前端在
`apps/web`, 两者各自的 `Dockerfile` 由对应负责人维护。

```
infra/
├── mysql/init/01-init.sql      # MySQL 首次初始化: 字符集 sanity + 库默认字符集兜底(幂等)
├── redis/redis.conf            # Redis 配置范例(文档化的备选方案, 见下文说明)
├── minio/README.md             # 桶创建 / 预签名 URL 可达性 / 生产反代考量
├── nginx/README.md             # 两层代理拓扑 / WebSocket 升级 / 推荐生产拓扑
├── dockerignore/               # ⚠️ 不是自动生效的, 需复制到 apps/* (见第 5 节)
│   ├── api.dockerignore
│   └── web.dockerignore
└── README.md                   # 本文件

仓库根目录:
├── docker-compose.yml          # 生产/准生产编排
└── docker-compose.dev.yml      # 本地开发覆盖文件
```

---

## 1. 快速开始

```powershell
# 1) 准备环境变量(会被 .gitignore 忽略, 必须本地生成)
copy .env.example .env
#   按需修改密码/端口; 至少改掉 MYSQL_ROOT_PASSWORD / MYSQL_PASSWORD /
#   REDIS_PASSWORD / MINIO_ROOT_PASSWORD / SECRET_KEY

# 2) 生产/准生产: 全量启动(含 api、web)
docker compose --env-file .env up -d --build

# 3) 本地开发: 只启动基础设施(api/web 被放在 "full" profile, 默认不启动)
docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml up -d
#   等价的显式写法(最稳妥, 不依赖 profile 语义):
docker compose --env-file .env up -d mysql redis minio createbuckets

# 3b) 容器化后端热重载(改 apps/api 代码即生效; 前端在宿主机 `pnpm dev`)
docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml `
  --profile dev up -d mysql redis minio createbuckets api-dev

# 3c) 连容器化前端 dev server 一起跑(Vite, 5173)
docker compose --env-file .env -f docker-compose.yml -f docker-compose.dev.yml `
  --profile dev up -d mysql redis minio createbuckets api-dev web-dev

# 4) 访问
#    前端        http://127.0.0.1:8080        (${WEB_PORT})
#    前端 dev    http://127.0.0.1:5173        (${WEB_DEV_PORT:-5173}, 仅 3c)
#    后端 OpenAPI http://127.0.0.1:8000/docs   (${API_PORT})
#    后端探针    http://127.0.0.1:8000/api/v1/health/live
#    MinIO 控制台 http://127.0.0.1:9001        (${MINIO_CONSOLE_PORT})
```

> 端口冲突提醒: `api-dev` 与生产 `api` 都用 `${API_PORT}`, 不要同时启动。
> 推荐按场景 3 / 3b / 3c 分开跑, 而不是 `--profile full --profile dev up -d`。

常用命令:

```powershell
docker compose ps -a                       # 含已退出的一次性任务 createbuckets
docker compose logs -f api                 # 跟随后端日志(entrypoint 会跑 alembic + 演示数据)
docker compose up -d --force-recreate createbuckets   # 重建桶
docker compose down                        # 停止, 保留命名卷
docker compose down -v                     # ⚠️ 连带删除数据卷
```

---

## 2. 服务一览

| 服务 | 镜像 | 宿主机端口 | 作用 | 依赖 |
| --- | --- | --- | --- | --- |
| `mysql` | `mysql:8.4` | `${MYSQL_PORT}:3306` | 主数据库, utf8mb4 / utf8mb4_0900_ai_ci | — |
| `redis` | `redis:7.4-alpine` | `${REDIS_PORT}:6379` | 缓存 / 会话 / WebSocket 广播, AOF 持久化 | — |
| `minio` | `minio/minio:latest` | `${MINIO_API_PORT}:9000`, `${MINIO_CONSOLE_PORT}:9001` | S3 兼容对象存储 | — |
| `createbuckets` | `minio/mc:latest` | — | 一次性: 建桶 + 匿名只读策略后退出 | minio(healthy) |
| `api` | 构建 `apps/api/Dockerfile` | `${API_PORT}:8000` | FastAPI 后端, 入口跑 alembic + 初始数据 | mysql/redis/minio(healthy) |
| `web` | 构建 `apps/web/Dockerfile` | `${WEB_PORT}:80` | 前端静态资源 + nginx 代理 `/api`、`/ws` | api |
| `api-dev` | 构建 `apps/api/Dockerfile` | `${API_PORT}:8000` | *(dev profile)* 后端热重载, `uvicorn --reload`, 挂载 `apps/api` | mysql/redis/minio(healthy) |
| `web-dev` | `node:22-alpine` | `${WEB_DEV_PORT:-5173}:5173` | *(dev profile)* Vite 开发服务器, 挂载 `apps/web` | api-dev |

所有服务位于同一 bridge 网络 `${COMPOSE_PROJECT_NAME}_app_net`, 通过服务名互访
(`mysql:3306`、`redis:6379`、`minio:9000`、`api:8000`、`api-dev:8000`)。
`api-dev` / `web-dev` 只在 `dev` profile 下存在, 详见 `docker-compose.dev.yml` 头部注释。

---

## 3. 环境变量策略

- **不硬编码任何密钥**。compose 中使用两种形式:
  - `${VAR:?错误提示}` —— 关键密钥缺失时 `docker compose up` 直接报错退出(快速失败);
  - `${VAR:-默认值}` —— 端口、时区、桶名等非敏感项给默认值。
- `api` 同时使用 `env_file: .env`(把整套配置注入容器)与 `environment:` 覆盖:
  容器内互访必须用**服务名**, 因此 `DATABASE_URL`、`REDIS_URL`、`MINIO_ENDPOINT`
  被显式覆盖为 `mysql` / `redis` / `minio`; 而 `MINIO_PUBLIC_ENDPOINT` 保留宿主机地址,
  因为**预签名 URL 是给浏览器用的**(详见 `infra/minio/README.md`)。
- 只启动基础设施、在宿主机裸跑后端时, 记得把 `.env` 中的 host 换成 `127.0.0.1`:

  ```
  DATABASE_URL=mysql+aiomysql://sg4:<pwd>@127.0.0.1:3306/sg4?charset=utf8mb4
  REDIS_URL=redis://:<pwd>@127.0.0.1:6379/0
  MINIO_ENDPOINT=127.0.0.1:9000
  ```

- 后端入口读取的开关: `RUN_MIGRATIONS`、`AUTO_CREATE_TABLES`、`SEED_DEMO_DATA`、
  `UVICORN_WORKERS`。生产建议 `AUTO_CREATE_TABLES=0`、`SEED_DEMO_DATA=0`。

---

## 4. 关于 `infra/redis/redis.conf`

compose 里 Redis 采用**命令行参数**启动
(`--requirepass`、`--appendonly yes`、`--maxmemory 512mb`、`--maxmemory-policy allkeys-lru`),
好处是密码直接来自 `.env`、不需要额外的入口脚本。

`infra/redis/redis.conf` 是等价的**配置文件写法**(已按段注释), 适合参数变多或需要精细
调优(慢查询、命令重命名、快照策略)时切换。切换方法写在文件头部注释里: 在 compose 的
`redis.command` 中指定 `["redis-server", "/usr/local/etc/redis/redis.conf"]` 并把该文件
挂载为只读。注意 **compose 不会替换被挂载配置文件里的变量**, 所以文件里的 `requirepass`
是占位符, 切换后需要自行注入真实密码(或保留命令行 `--requirepass` 与配置文件并用,
后者优先级更高)。

---

## 5. `.dockerignore`(必须手动复制)

出于仓库分工约束, 本目录提供的忽略清单**不会自动生效**。启用方式:

```powershell
copy infra\dockerignore\api.dockerignore apps\api\.dockerignore
copy infra\dockerignore\web.dockerignore apps\web\.dockerignore
```

*.dockerignore 文件在 Windows 资源管理器里不好直接创建(名称以点开头), 用上面的
`copy`/`Copy-Item` 最方便。若对应负责人已有自己的 `.dockerignore`, 请合并而不是覆盖 ——
尤其不要忽略前端构建必需的 `src/`、`public/`、`index.html`、`nginx.conf`。

---

## 6. 校验与自检

```powershell
# 语法校验(不启动任何容器, 不拉取镜像)
docker compose --env-file .env.example -f docker-compose.yml config
docker compose --env-file .env.example -f docker-compose.yml -f docker-compose.dev.yml config

# 服务/卷/网络清单
docker compose --env-file .env.example config --services
docker compose --env-file .env.example config --volumes

# 只校验开发覆盖文件的 profile 行为(列出默认会启动的服务)
docker compose --env-file .env.example -f docker-compose.yml config --services
```

> 注意: 上面用 `--env-file .env.example` 只是为了让校验在**没有** `.env` 的干净检出上
> 也能通过。实际运行请使用 `.env`(内容不同, 尤其是密码)。

启动后的健康检查:

```powershell
docker compose ps                                   # 看 healthy 状态
docker compose ps -a                                # 含 Exited(0) 的 createbuckets
docker compose exec redis redis-cli -a "$env:REDIS_PASSWORD" --no-auth-warning ping
docker compose exec mysql mysqladmin ping -h 127.0.0.1 -u"$env:MYSQL_USER" -p"$env:MYSQL_PASSWORD"
curl.exe -s http://127.0.0.1:8000/api/v1/health/live
docker compose logs createbuckets                   # 应看到 "[createbuckets] 完成: sg4-files"
```

---

## 7. 已知边界与注意事项

1. **`version:` 字段已弃用**, 两个 compose 文件均未声明 —— 这样在新版 `docker compose`
   (v2+, 本项目实测 v5.5.1)下不会产生 obsolete 警告, 同时依赖 top-level `name:`。
2. 生产 `api` 服务**不做 bind mount**, 代码固化在镜像里; 只有 `docker-compose.dev.yml`
   的 `dev` profile 才挂载源码做热重载。
3. `createbuckets` 是一次性任务, 设计上会以 `Exited (0)` 结束, 这是正常的, 不是崩溃。
   `restart: "no"` 保证它不会反复重启。
4. 开发要同时跑容器化前后端时, 加 `--profile full`(生产镜像); 热重载用 `--profile dev`
   (`api-dev` / `web-dev`)。`api-dev` 与 `api` 争用同一端口, `web-dev`(5173)与
   `web`(8080)不冲突, 但请按场景分开启动, 不要 `--profile full --profile dev` 一把梭。
5. `web-dev` **刻意不复用前端生产镜像** —— `apps/web/Dockerfile` 的运行阶段是
   `nginx:1.27-alpine`, 里面没有 node/pnpm; 因此 `web-dev` 直接用 `node:22-alpine` +
   corepack(pnpm 9.12), 并把 `node_modules` 放在命名卷
   `${COMPOSE_PROJECT_NAME}_web_node_modules` 里, 避免与宿主机的 Windows 依赖互相覆盖。
   另外 `apps/web/vite.config.ts` 的 `server.host` 是 `127.0.0.1`(容器内回环), 必须由
   `--host 0.0.0.0` 覆盖, compose 文件中已这样写。
   若不想用容器跑前端, 直接在宿主机 `pnpm dev` 即可(场景 A / 3b 都支持)。
6. 数据库迁移由后端 `alembic` 负责, `infra/mysql/init/01-init.sql` **不建业务表**,
   只做字符集检查与库默认字符集兜底。
7. 本机 3306/6379/9000 端口若已被占用, 改 `.env` 里对应的 `*_PORT` 即可
   (容器内部端口不变, 服务间通信不受影响)。生产环境建议把基础设施端口绑定到
   `127.0.0.1`, 例如 `"127.0.0.1:${MYSQL_PORT}:3306"`。
   注意 `WEB_DEV_PORT` 未写入根 `.env.example`(该文件不属于本次改动范围), 用默认值
   `5173`; 如需修改, 在启动命令前加环境变量或自行补进 `.env`。
8. **前置依赖**: `apps/web` 的 `Dockerfile` 与 `nginx.conf`、`apps/api` 的 `Dockerfile`
   均已就位, 且与本节第 8 条核对表一致。若前端后续改了 `nginx.conf` 的监听端口或代理
   路径, 请同步复核本编排。

---

## 8. 与前后端镜像的对接核对(已按实际文件校验)

以下几条是本编排与 `apps/api`、`apps/web` 实际实现的对接点, 改动任一侧时请同步:

| 对接点 | 本编排 | 实现侧 | 状态 |
| --- | --- | --- | --- |
| api 端口 | `expose/ports 8000` | `scripts/start.sh`: uvicorn `--port 8000`, `UVICORN_WORKERS` | ✅ |
| api 健康探针 | `curl -fsS .../api/v1/health/live` | 镜像内含 `curl`; 路由 `/api/v1/health/live` | ✅ |
| 迁移/初始化开关 | `RUN_MIGRATIONS` / `AUTO_CREATE_TABLES` / `SEED_DEMO_DATA` | `scripts/start.sh` 读取这三个变量 | ✅ |
| 依赖等待 | `depends_on: mysql/redis/minio healthy` | `start.sh` 另有 60 次 MySQL 等待兜底 | ✅ |
| web 端口 | `"${WEB_PORT}:80"` | `apps/web/nginx.conf`: `listen 80` | ✅ |
| web 健康探针 | wget 检查 `/`, 接受 1xx–4xx | `nginx:1.27-alpine` 自带 wget; 镜像内探针亦为 `wget` | ✅ |
| REST 代理 | 依赖 web 容器代理 `/api/` | `location /api/ { proxy_pass http://sg4_api; }` → `api:8000` | ✅ |
| WebSocket | 依赖 web 容器代理 `/ws` | `location /ws` 带 `Upgrade`/`Connection`, `proxy_read_timeout 3600s` | ✅ |
| 上传体积 | — | nginx `client_max_body_size 64m`; 后端 `MAX_UPLOAD_SIZE_MB=50` | ⚠️ 见下 |
| CORS | `.env` 的 `CORS_ORIGINS` 含 `8080` 与 `5173` | `settings.cors_origin_list` 逗号分隔解析 | ✅ |
| MinIO 双地址 | 容器内 `MINIO_ENDPOINT=minio:9000`, 对外 `MINIO_PUBLIC_ENDPOINT=127.0.0.1:9000` | `minio_client.get_minio_public()` 用后者生成预签名 URL | ✅ |

`docker-compose.yml` 里 `api` 的 `healthcheck` 显式声明了一次(与镜像内 `HEALTHCHECK`
语义相同): compose 层的定义优先级更高, 便于统一调整 interval/retries 而不必改镜像。

⚠️ **唯一一处数值不一致(不属于本次改动范围, 仅提示)**: `apps/web/nginx.conf` 的
`client_max_body_size 64m` 比后端 `MAX_UPLOAD_SIZE_MB=50` 宽松。表现为 50–64MB 的文件
会被 nginx 放行、再由后端拒绝(返回业务错误而非 413)。如需完全对齐, 请由前端把
`client_max_body_size` 改为 `50m`, 或由后端调整 `MAX_UPLOAD_SIZE_MB`。


