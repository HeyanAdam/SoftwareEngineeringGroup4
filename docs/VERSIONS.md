# 配置与依赖版本清单

> 本文件由 `python tools/gen-versions.py` 自动生成，**请勿手工编辑**。
> 新增或升级依赖后重新执行该脚本即可刷新。

生成时间：2026-09-16 20:56

## 1. 版本总览（照这张表装环境就不会错）

| 组件 | 版本要求 | 说明 |
| --- | --- | --- |
| Node.js | `^22.18.0 || >=24.12.0` | 前端 `engines` 约束，低于此版本会报 `EBADENGINE` |
| npm | 随 Node 附带（10+） | 本清单按 npm 生成 |
| Python | `>=3.11` | 后端 `requirements.txt` 与语法所要求 |
| MySQL | 见第 4 节 | 容器镜像 |
| Redis | 见第 4 节 | 容器镜像 |
| MinIO | 见第 4 节 | 容器镜像 |
| Docker Desktop | 最新版（含 Compose v2） | 用于一键起基础设施 |

## 2. 前端依赖（kaoyan-frontend/package.json）

### 2.1 运行依赖

| 包 | 版本约束 | lockfile 锁定版本 |
| --- | --- | --- |
| `@element-plus/icons-vue` | `^2.3.0` | `未锁定` |
| `axios` | `^1.7.0` | `未锁定` |
| `echarts` | `^5.6.0` | `未锁定` |
| `element-plus` | `^2.9.0` | `未锁定` |
| `pinia` | `^4.0.2` | `4.0.3` |
| `vue` | `^3.5.40` | `3.5.42` |
| `vue-router` | `^5.2.0` | `5.3.1` |

### 2.2 开发依赖

| 包 | 版本约束 | lockfile 锁定版本 |
| --- | --- | --- |
| `@tsconfig/node24` | `^24.0.4` | `24.0.5` |
| `@types/node` | `^24.13.3` | `24.13.4` |
| `@vitejs/plugin-vue` | `^6.0.8` | `6.0.9` |
| `@vue/eslint-config-typescript` | `^14.9.0` | `14.9.0` |
| `@vue/tsconfig` | `^0.9.1` | `0.9.1` |
| `eslint` | `^10.7.0` | `10.10.0` |
| `eslint-config-prettier` | `^10.1.8` | `10.1.8` |
| `eslint-plugin-oxlint` | `~1.74.0` | `1.73.0` |
| `eslint-plugin-vue` | `~10.9.2` | `10.9.2` |
| `jiti` | `^2.7.0` | `2.7.0` |
| `npm-run-all2` | `^9.0.2` | `9.0.3` |
| `oxlint` | `~1.74.0` | `1.74.0` |
| `prettier` | `3.9.5` | `3.9.5` |
| `sass` | `^1.80.0` | `未锁定` |
| `typescript` | `~6.0.0` | `6.0.3` |
| `vite` | `^8.1.5` | `8.3.0` |
| `vite-plugin-vue-devtools` | `^8.1.5` | `8.2.1` |
| `vue-eslint-parser` | `^10.4.1` | `10.4.1` |
| `vue-tsc` | `^3.3.7` | `3.3.11` |

> ⚠️ **lockfile 未同步**：以下包在 `package-lock.json` 里找不到，说明 lockfile 落后于
> `package.json`。此时 **`npm ci` 会失败**，请执行 `npm install` 重建 lockfile：
>
> ```
> @element-plus/icons-vue、axios、echarts、element-plus、sass
> ```

### 2.3 前端脚本

| 命令 | 实际执行 |
| --- | --- |
| `npm run dev` | `vite` |
| `npm run build` | `run-p type-check "build-only {@}" --` |
| `npm run preview` | `vite preview` |
| `npm run build-only` | `vite build` |
| `npm run type-check` | `vue-tsc --build` |
| `npm run lint` | `run-s "lint:*"` |
| `npm run lint:oxlint` | `oxlint . --fix` |
| `npm run lint:eslint` | `eslint . --fix --cache` |
| `npm run format` | `prettier --write --experimental-cli src/` |

## 3. 后端依赖（kaoyan-backend/requirements.txt）

| 包 | 版本约束 | 说明 |
| --- | --- | --- |
| `fastapi` | `>=0.110,<1.0` | - |
| `uvicorn[standard]` | `>=0.27,<1.0` | - |
| `python-multipart` | `>=0.0.9` | 表单 / 文件上传 |
| `pydantic` | `>=2.5,<3.0` | - |
| `python-dotenv` | `>=1.0,<2.0` | 读取 .env |
| `SQLAlchemy` | `>=2.0,<3.0` | - |
| `PyMySQL` | `>=1.1,<2.0` | - |
| `cryptography` | `>=42.0` | MySQL 8 caching_sha2_password 认证需要 |
| `alembic` | `>=1.13,<2.0` | 数据库迁移(逐步替换 create_all) |
| `redis` | `>=5.0,<7.0` | - |
| `minio` | `>=7.2,<8.0` | - |
| `argon2-cffi` | `>=23.1,<26.0` | 密码哈希(比 bcrypt 更省心, 无 72 字节限制) |
| `PyJWT` | `>=2.8,<3.0` | 签发/校验 access token |
| `websockets` | `>=12.0` | WebSocket 支持(uvicorn[standard] 已带, 显式声明更清晰) |

安装：`pip install -r requirements.txt`

## 4. 容器镜像与端口（docker-compose.yml）

| 服务 | 镜像 | 容器名 | 宿主机端口 → 容器端口 |
| --- | --- | --- | --- |
| `mysql` | `mysql:8.0` | `kaoyan-mysql` | `3307:3306` |
| `redis` | `redis:7-alpine` | `kaoyan-redis` | `6379:6379` |
| `minio` | `quay.io/minio/minio` | `kaoyan-minio` | `9000:9000, 9001:9001` |

启动：`docker compose up -d`　　停止：`docker compose down`（加 `-v` 会清空数据）

## 5. 后端运行配置（kaoyan-backend/.env.example 默认值）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DB_HOST` | `localhost` | 注意: docker-compose.yml 把容器 3306 映射到了宿主机 3307, 所以这里必须是 3307 |
| `DB_PORT` | `3307` | - |
| `DB_USER` | `root` | - |
| `DB_PASSWORD` | `kaoyan123` | - |
| `DB_NAME` | `kaoyan` | - |
| `REDIS_HOST` | `localhost` | - |
| `REDIS_PORT` | `6379` | - |
| `REDIS_DB` | `0` | - |
| `REDIS_PASSWORD` | （空） | compose 里的 Redis 未设密码, 留空即可; 若自己加了 requirepass 再填 |
| `MINIO_ENDPOINT` | `localhost:9000` | - |
| `MINIO_ACCESS_KEY` | `minioadmin` | - |
| `MINIO_SECRET_KEY` | `minioadmin` | - |
| `MINIO_BUCKET` | `kaoyan` | - |
| `MINIO_SECURE` | `false` | 是否使用 HTTPS(本地容器为 http, 保持 false) |
| `BACKEND_HOST` | `127.0.0.1` | - |
| `BACKEND_PORT` | `8001` | - |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 允许跨域的前端地址, 多个用英文逗号分隔 |
| `SECRET_KEY` | `dev-only-change-me-please-0123456789abcdef` | python -c "import secrets; print(secrets.token_urlsafe(48))" |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | - |
| `JWT_ALGORITHM` | `HS256` | - |

> 这些默认值与第 4 节的容器配置一一对应，克隆后 `copy .env.example .env` 即可直接使用。

## 6. 环境自检清单

```powershell
node -v            # 应满足第 1 节的 Node 版本要求
python --version   # 应 >= 3.11
docker compose version
```

| 报错关键词 | 含义 | 处理 |
| --- | --- | --- |
| `EBADENGINE` | Node 版本不满足 `engines` | 升级 Node 到第 1 节要求的版本 |
| `ERESOLVE` + `peer` | 两个包的版本约束冲突 | 对齐版本约束 |
| `... in sync` / `Missing: xxx from lock file` | lockfile 与 package.json 不一致 | 用 `npm install`（**不是** `npm ci`）重建 |
| `ETIMEDOUT` / `ECONNRESET` | 网络问题 | `npm config set registry https://registry.npmmirror.com` |

