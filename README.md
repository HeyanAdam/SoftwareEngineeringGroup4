# 考研 AI 导学平台

面向考研学生的 **AI 陪伴式导学平台**。当前仓库处于「脚手架 + 模块骨架」阶段：基础设施、前后端框架与模块划分已就绪，业务功能按模块逐步填充。

- **项目定位**：面向考研学生的 AI 陪伴式导学平台
- **核心功能**：RAG 问答、用户画像、个性化规划、推荐评分、多模态问答
- **实施原则**：模块化单体，先跑通学习闭环，再扩展语音与数字人

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue3 + TypeScript + Vite + Pinia + Vue Router + Element Plus + ECharts |
| 后端 | Python + FastAPI + SQLAlchemy |
| 数据库 | MySQL + Redis + MinIO |
| 实时通信 | WebSocket |
| 部署 | Docker Compose |

## 目录结构

```text
SoftwareEngineeringGroup4/
├── kaoyan-frontend/            前端项目（Vue3 + Vite）
│   ├── src/
│   │   ├── api/                接口封装（按后端模块划分）
│   │   ├── layouts/            页面布局（侧边栏 + 顶栏）
│   │   ├── router/             路由表与登录守卫
│   │   ├── stores/             Pinia 状态（用户信息等）
│   │   ├── types/              与后端契约一致的 TS 类型
│   │   ├── utils/              axios 实例（统一错误处理、自动带 token）
│   │   └── views/              页面（首页 / AI 问答 / 学习计划 / 个人中心 / 登录注册）
│   ├── vite.config.ts          开发代理：/api → 后端 8001
│   └── package.json
│
├── kaoyan-backend/             后端项目（FastAPI）
│   ├── app/
│   │   ├── main.py             入口：CORS、注册各模块路由
│   │   ├── core/               配置与数据库连接
│   │   │   ├── config.py       读取 .env
│   │   │   ├── database.py     SQLAlchemy 引擎与会话
│   │   │   ├── security.py     密码哈希与 JWT
│   │   │   └── deps.py         依赖注入（当前登录用户）
│   │   ├── models/             ORM 模型（用户、会话、消息、计划…）
│   │   ├── schemas/            请求/响应模型
│   │   └── modules/            业务模块
│   │       ├── user/           用户模块：注册 / 登录 / 个人信息
│   │       ├── ai_chat/        AI 对话：会话、消息、问答
│   │       └── study_plan/     学习规划：计划、任务、进度
│   ├── requirements.txt
│   └── .env.example
│
├── docker-compose.yml          一键启动 MySQL + Redis + MinIO
├── README.md
├── 大学生考研AI导学系统需求分析文档 .docx
└── 开发规范1.0.pdf
```

## 环境准备

第一次使用需要安装 4 个工具：

| 工具 | 版本要求 | 下载地址 |
| --- | --- | --- |
| Node.js | **22.18+ 或 24.12+**（前端 `engines` 与 `@tsconfig/node24` 要求，20 及以下不保证可用） | https://nodejs.org |
| Python | 3.11+ | https://www.python.org |
| Git | 任意 | https://git-scm.com |
| Docker Desktop | 最新版 | https://www.docker.com/products/docker-desktop/ |

> **Windows 用户注意**
> - 安装 Python 时必须勾选 **Add Python to PATH**
> - 安装 Docker Desktop 需要先装 WSL2（安装程序会自动提示）
> - 命令行示例以 PowerShell 为准，`copy` 即复制文件

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/HeyanAdam/SoftwareEngineeringGroup4.git
cd SoftwareEngineeringGroup4
```

### 2. 启动数据库（MySQL + Redis + MinIO）

```bash
docker compose up -d
docker ps
```

应看到 3 个容器：`kaoyan-mysql`、`kaoyan-redis`、`kaoyan-minio`。

### 3. 启动后端

```bash
cd kaoyan-backend
python -m venv venv
venv\Scripts\activate            # macOS / Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env           # 模板里的端口/口令已与 docker-compose 对齐, 无需修改
uvicorn app.main:app --reload --port 8001
```

验证：浏览器打开 http://127.0.0.1:8001/docs 能看到 Swagger 接口文档。

### 4. 启动前端

新开一个终端：

```bash
cd kaoyan-frontend
npm install
npm run dev
```

验证：浏览器打开 http://localhost:5173 。

## 常用命令速查

| 操作 | 命令 |
| --- | --- |
| 启动数据库 | `docker compose up -d` |
| 停止数据库 | `docker compose down` |
| 查看容器状态 | `docker ps` |
| 启动后端 | `cd kaoyan-backend` → `venv\Scripts\activate` → `uvicorn app.main:app --reload --port 8001` |
| 启动前端 | `cd kaoyan-frontend` → `npm run dev` |
| 前端类型检查 | `cd kaoyan-frontend` → `npm run type-check` |
| 前端构建 | `cd kaoyan-frontend` → `npm run build` |

## 服务与端口

| 服务 | 端口 | 用途 | 账号 |
| --- | --- | --- | --- |
| 前端 | 5173 | 开发服务器 | — |
| 后端 | 8001 | API / Swagger | — |
| MySQL | **3307** → 容器 3306 | 用户、会话、计划等业务数据 | `root` / `kaoyan123`，库 `kaoyan` |
| Redis | 6379 | 缓存、会话状态 | 无密码 |
| MinIO | 9000 API / 9001 控制台 | 多模态文件 | `minioadmin` / `minioadmin` |

## 接口一览

| 地址 | 说明 |
| --- | --- |
| http://127.0.0.1:8001/ | 后端根接口（启动确认） |
| http://127.0.0.1:8001/docs | Swagger 接口文档 |
| `/api/db-check` | 数据库连接测试（返回 MySQL 版本） |
| `/api/user/*` | 用户模块：注册 / 登录 / 个人信息 |
| `/api/ai/*` | AI 对话模块：会话、消息、问答 |
| `/api/plan/*` | 学习规划模块：计划、任务、进度 |

> 各模块的详细接口以 http://127.0.0.1:8001/docs 为准，并随代码更新。

## 协作方式

1. **不要直接往 `main` 推代码**。每条改动开一个分支：`feat/xxx`、`fix/xxx`、`docs/xxx`。
2. 提交信息写清楚做了什么：`feat: 新增用户注册接口`、`fix: 修正 MySQL 端口`。
3. 推送后在 GitHub 上开 Pull Request，至少 1 人 Review 通过再合并。
4. 每人只改自己负责的模块目录，避免多人同时改同一个文件。
5. 数据库结构变更请同步更新 `app/models/`，并在 PR 说明里写清字段变化。

## 常见问题

| 问题 | 处理 |
| --- | --- |
| `docker compose up -d` 卡住不动 | 国内网络问题，在 Docker Desktop → Settings → Docker Engine 配置镜像加速器 |
| `uvicorn` 不是内部或外部命令 | 虚拟环境没激活，执行 `venv\Scripts\activate` |
| 后端启动报错连不上 MySQL | 检查 `.env` 的 `DB_PORT` 是否为 **3307**（compose 映射到 3307，不是 3306） |
| 端口被占用 | 改 `docker-compose.yml` 里的端口映射，或停掉占用端口的程序 |
| 前端请求后端报 CORS / 404 | 确认后端已启动在 8001，前端通过 `vite.config.ts` 里的 `/api` 代理转发 |
| 前端 `npm install` 失败 | 切换镜像源：`npm config set registry https://registry.npmmirror.com` |

## 团队成员

| 组别 | 成员 |
| --- | --- |
| 前端组 | 待补充 |
| 后端组 | 待补充 |
| AI 组 | 待补充 |

## 相关文档

- 《大学生考研AI导学系统需求分析文档 .docx》—— 需求与用例
- 《开发规范1.0.pdf》—— 编码规范与协作约定
- [kaoyan-backend/README.md](kaoyan-backend/README.md) —— 后端开发说明
