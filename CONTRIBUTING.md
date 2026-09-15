# 协作规范 (Contributing Guide)

> 本文是小组协作的**唯一约定来源**。请先读完再提交代码。

## 目录

- [1. 分支模型](#1-分支模型)
- [2. 提交信息规范](#2-提交信息规范)
- [3. 开发流程](#3-开发流程)
- [4. 代码规范](#4-代码规范)
- [5. 数据库变更](#5-数据库变更)
- [6. 接口约定](#6-接口约定)
- [7. 评审与合并](#7-评审与合并)
- [8. 常见问题](#8-常见问题)

---

## 1. 分支模型

采用轻量 Git Flow:

| 分支 | 命名 | 用途 | 保护 |
| --- | --- | --- | --- |
| `main` | `main` | 随时可部署的稳定版本 | ✅ 禁止直接 push, 需 PR + 1 人评审 |
| `develop` | `develop` | 集成分支, 功能汇总 | ✅ 需 PR |
| 功能 | `feat/<模块>-<简述>` | 新功能, 例 `feat/api-file-presign` | — |
| 修复 | `fix/<模块>-<简述>` | 缺陷修复, 例 `fix/web-token-refresh` | — |
| 文档 | `docs/<简述>` | 只改文档 | — |
| 发布 | `release/vX.Y.Z` | 发布准备 | — |
| 热修 | `hotfix/<简述>` | 紧急修复线上 | — |

规则:

1. **永远从最新的 `develop` 切分支**: `git switch develop && git pull && git switch -c feat/web-dashboard`
2. 一个分支只做一件事, 生命周期尽量 < 3 天; 太大就拆成多个 PR。
3. 定期 `git rebase develop` 保持同步, 避免巨型冲突。
4. 合并后删除分支。

```bash
# 推荐工作流
git switch develop && git pull --rebase
git switch -c feat/api-role-permission
# ... 开发 ...
git add -A && git commit -m "feat(api): 角色支持权限点批量分配"
git fetch origin && git rebase origin/develop
git push -u origin feat/api-role-permission
# 在 GitHub 上开 PR, base 选 develop
```

## 2. 提交信息规范

必须符合 [Conventional Commits](https://www.conventionalcommits.org/), CI 会校验 (`commit-lint.yml`):

```
<type>(<scope>): <subject>

[body]

[footer]
```

- `type` 取值: `feat` `fix` `docs` `style` `refactor` `perf` `test` `build` `ci` `chore` `revert`
- `scope` 建议: `web` `api` `db` `ws` `files` `infra` `ci` `docs` `deps`
- `subject` 用中文或英文均可, 不要大写开头, 结尾不加句号, 建议 ≤ 50 字

```text
feat(web): 仪表盘新增角色分布环形图
fix(api): 修复刷新令牌并发请求导致误判失效
docs: 补充 MinIO 预签名地址的浏览器可达性说明
refactor(api): 抽出 BaseService 统一分页逻辑
build(deps): 升级 fastapi 到 0.115.6
```

一次提交只做一类改动。禁止 `update`、`fix bug`、`111` 这类信息。

## 3. 开发流程

```
Issue/Task -> 分支 -> 开发自测 -> PR -> CI 绿 -> 评审 -> 合并 -> 删分支
```

1. **先有 Issue**: 每个 PR 必须关联 Issue (`closes #12`)。
2. **本地起环境**:

   ```bash
   cp .env.example .env          # Windows: copy .env.example .env
   pnpm up:infra                 # 只起 mysql/redis/minio
   pnpm api:dev                  # 后端 http://127.0.0.1:8000/api/v1/docs
   pnpm dev                      # 前端 http://127.0.0.1:5173
   # 或者一条命令全栈容器化: pnpm up  ->  http://localhost:8080
   ```

3. **提 PR 前必须自测**: 至少跑通后端 `pytest` 与前端 `type-check` + `test` + `build`。
4. **PR 描述**按模板填写, UI 变更附截图。

## 4. 代码规范

### 后端 (`apps/api`)

- 遵循 PEP 8, 行宽 100, 统一由 `ruff` 把关: `pnpm api:lint` (`ruff check`) + `ruff format`。
- 分层: `api/v1`(路由/参数校验) → `services`(业务) → `models`(ORM) / `core`(基础设施)。**路由里不写 SQL, service 里不依赖 FastAPI 对象**。
- 所有对外失败抛 `app.core.exceptions` 里的异常类, 不要 `raise HTTPException` 混用。
- 异步优先: 阻塞库(如 minio-py)必须 `asyncio.to_thread` 包装。
- 新增依赖加到 `pyproject.toml`, 不要手写 requirements.txt。

### 前端 (`apps/web`)

- TypeScript 严格模式, 禁止无理由 `any`; 所有接口返回类型写在 `src/types`。
- 组件用 `<script setup lang="ts">`; 组合式函数放 `src/composables`。
- 样式用 SCSS + CSS 变量, 不引入新的 UI 框架/原子化框架, 保持 Element Plus 统一。
- 提交前跑 `pnpm --filter @app/web lint` 与 `format`。

### 通用

- 不提交密钥、口令、`.env`、`data/`、`dist/`、`node_modules/`。
- 新增配置项必须**同时**更新 `.env.example` 与 `docs/ENV.md`。

## 5. 数据库变更

**任何表结构变更都必须走 Alembic, 不允许手改数据库。**

```bash
cd apps/api
# 1. 修改 app/models/*.py
# 2. 生成迁移
alembic revision --autogenerate -m "add table xxx"
# 3. 人工检查 alembic/versions/xxx.py (务必确认 drop/alter 是否符合预期!)
# 4. 本地验证
alembic upgrade head
alembic downgrade -1 && alembic upgrade head
# 5. 随 PR 一起提交迁移文件
```

- 迁移文件名与 revision 必须入库, PR 评审时重点看 `upgrade()` 与 `downgrade()` 是否对称。
- 破坏性变更(删列/改类型)必须先加新列 + 数据回填, 下个版本再删旧列。

## 6. 接口约定

- 统一前缀 `/api/v1`, 统一错误信封:

  ```json
  { "code": 40300, "message": "没有权限执行该操作", "data": null }
  ```

  业务码规则: `HTTP状态码 * 100 + 序号`。前端只认 `message` 直接弹提示, 需要分支时用 `code`。
- 分页统一: 入参 `page` / `page_size`, 出参 `{ "items": [...], "meta": { "page","page_size","total","pages" } }`。
- 时间统一 ISO 8601 UTC 字符串。
- 新增/修改接口必须带 `summary` 与 `response_model`, 保证 `/docs` 可用; 前端类型定义同步更新。
- WebSocket 消息协议见 `apps/api/app/schemas/ws.py` 顶部注释, 改动协议需前后端同时评审。

## 7. 评审与合并

- 至少 **1 位** 评审人通过 (`CODEOWNERS` 会自动请求)。
- 所有 CI 检查必须绿: `Backend CI` / `Frontend CI` / `Commit Lint` / `Security Scan`。
- 评审关注: 是否有测试、是否泄露密钥、错误处理是否完整、是否有 N+1 查询、前端是否处理加载/空/错误三态。
- 合并方式: **Squash and merge** (保持 `main`/`develop` 历史线性且信息规范)。
- 禁止 `--force push` 到 `main` / `develop`。

## 8. 常见问题

| 问题 | 处理 |
| --- | --- |
| 端口被占用 | 改 `.env` 里的 `*_PORT`, 重新 `docker compose up -d` |
| 登录后 401 循环 | 检查 `.env` 的 `SECRET_KEY` 是否被改导致旧 token 失效, 清 localStorage 重登 |
| WebSocket 连不上 | 确认 nginx/vite 代理带 `Upgrade` 头; 浏览器 DevTools -> Network -> WS 看握手响应 |
| 上传文件 403 | 检查 `MINIO_PUBLIC_ENDPOINT` 是否浏览器可达, 以及桶权限 |
| 前端 build 内存溢出 | `NODE_OPTIONS=--max-old-space-size=4096 pnpm build` |
| CI 全红但本地正常 | 检查是否漏提交 `alembic/versions` 新文件或 `pnpm-lock.yaml` |

---

有任何规范不明确的地方, 直接在 Issue/Discussions 提出, 我们一起把这份文档改好。
