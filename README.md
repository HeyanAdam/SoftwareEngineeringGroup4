# 考研 AI 导学平台 · 鉴权与授权改造包

这是可直接覆盖到你项目里的生产代码，不是演示。骨架、命名、异常约定、接口契约全部沿用你上传的 FastAPI + Vue3 项目，只做鉴权与授权相关的增删改。

## 一、怎么用

1. 按下面的「文件去向」把文件复制到项目对应路径（同名文件直接覆盖，覆盖前建议先 `git commit`）。
2. `backend/sql/rbac_mysql.sql` 执行一次建表。
3. `.env.example` 的 `SECRET_KEY` 已换成随机值，复制成 `.env` 后按需填 `MAIL_*`。
4. `pip install -r requirements.txt`（新增了 `authx`、`email-validator`）。
5. 启动后端，`AUTO_SEED=true` 会自动写入 16 条权限、2 个内置角色、1 个初始管理员。
6. 前端 `npm install && npm run dev`，用 `admin / Admin@123456` 登录（上线前改掉）。

部署提醒：生产环境必须 `REDIS_ENABLED=true`（吊销名单与密码版本依赖它），否则启动自检会直接拒绝启动。

验收：`cd backend && python scripts/smoke_test.py`（22 个端点、7 张表的完整清单与验收步骤见 `docs/改造说明.md` 附录 A、B）。，应输出 `62 通过 / 0 失败`。

## 二、文件去向

### 后端 `backend/app/`

| 本包文件 | 覆盖到 | 说明 |
|---|---|---|
| `core/config.py` | `app/core/config.py` | 新增 RBAC / 验证码 / 邮件 / 管理员初始化配置，新增 `assert_secret_key_safe()` |
| `core/store.py` | `app/core/store.py` | **新增**，Redis / 内存双实现的 KV 存储 |
| `core/security.py` | `app/core/security.py` | 重写：AuthX 实例、令牌签发校验、吊销、密码版本、argon2、密码强度 |
| `core/deps.py` | `app/core/deps.py` | 重写：`get_current_user`、`DbSession`、`CurrentUser` |
| `core/rbac.py` | `app/core/rbac.py` | **新增**，权限计算与 `require_permission` |
| `core/audit.py` | `app/core/audit.py` | **新增**，审计写入 |
| `core/mailer.py` | `app/core/mailer.py` | **新增**，QQ SMTP SSL465 + 控制台兜底 |
| `core/seed.py` | `app/core/seed.py` | **新增**，权限/角色/管理员初始数据 |
| `models/types.py` | `app/models/types.py` | **新增**，跨库自增大整数主键 |
| `models/audit.py` | `app/models/audit.py` | **新增**，`sys_audit_log` |
| `models/user.py` | `app/models/user.py` | 重写：`sys_user`，属性名与列名解耦 |
| `models/account.py` | `app/models/account.py` | **新增**，`user_account` |
| `models/rbac.py` | `app/models/rbac.py` | **新增**，`sys_role` / `sys_permission` / 关联表 |
| `models/__init__.py` | `app/models/__init__.py` | 注册全部模型 |
| `schemas/user.py` | `app/schemas/user.py` | 扩充登录/改密/验证码 schema |
| `schemas/rbac.py` | `app/schemas/rbac.py` | **新增** |
| `modules/user/service.py` | `app/modules/user/service.py` | 重写（原文件未拿到，按 router 调用签名实现，详见 docs 第 13 节） |
| `modules/user/router.py` | `app/modules/user/router.py` | 重写：新增邮箱登录、发码、登出、改密、重置、权限查询 |
| `modules/rbac/__init__.py` | `app/modules/rbac/__init__.py` | **新增** |
| `modules/rbac/service.py` | `app/modules/rbac/service.py` | **新增** |
| `modules/rbac/router.py` | `app/modules/rbac/router.py` | **新增** |
| `main.py` | `app/main.py` | 挂载 rbac 路由、启动时校验密钥 + 写种子数据 |
| `requirements.txt` | `requirements.txt` | 追加 `authx`、`email-validator` |
| `.env.example` | `.env.example` | 追加 RBAC / 验证码 / 邮件 / 管理员配置，`SECRET_KEY` 已随机化 |
| `sql/rbac_mysql.sql` | 项目 `sql/` 下 | MySQL 8 建表脚本（由 ORM 导出） |
| `scripts/smoke_test.py` | 项目 `scripts/` 下 | 端到端自测，60 项断言 |

### 前端 `frontend/src/`

| 本包文件 | 覆盖到 |
|---|---|
| `types/user.ts` | `src/types/user.ts` |
| `types/rbac.ts` | `src/types/rbac.ts`（新增） |
| `api/auth.ts` | `src/api/auth.ts` |
| `api/rbac.ts` | `src/api/rbac.ts`（新增） |
| `stores/auth.ts` | `src/stores/auth.ts` |
| `config/menu.ts` | `src/config/menu.ts`（新增） |
| `router/routes.ts` | `src/router/routes.ts` |
| `router/index.ts` | `src/router/index.ts` |
| `layouts/DefaultLayout.vue` | `src/layouts/DefaultLayout.vue` |
| `utils/request.ts` | `src/utils/request.ts` |
| `views/LoginView.vue` | `src/views/LoginView.vue` |
| `views/ProfileView.vue` | `src/views/ProfileView.vue` |
| `views/RegisterView.vue` | `src/views/RegisterView.vue` |
| `views/admin/*.vue` | `src/views/admin/`（新增） |

`HomeView.vue`、`ChatView.vue`、`PlanView.vue` 不需要改。

## 三、超出《权限表》的部分只剩 3 类

完整理由见 `docs/改造说明.md` 第 3 节：

1. `sys_user.email`（邮箱验证码登录必须按邮箱反查，且必须唯一）
2. 新表 `sys_audit_log`（禅道 L3 的审计日志，权限表本身没有）
3. `uk_user_role` / `uk_role_perm` 唯一约束（防重复授权）

`user_account` 与 ER 图 12 个字段完全一致，原先多出来的 `exam_year` 与 `target_school_name` 已删除，个人中心表单同步改为 ER 原生字段（昵称/本科专业/报考专业/目标地区/备考阶段/目标分数）。

## 三·补：业务模块怎么接（本次不实现业务）

鉴权层只对外提供三个东西，业务模块自己引用，改造包不代写任何业务接口：

| 符号 | 位置 |
|---|---|
| `DbSession` | `app/core/deps.py` |
| `CurrentUser`（401/403/吊销都在这一层处理完） | `app/core/deps.py` |
| `require_permission("模块:操作")` | `app/core/rbac.py` |

```python
from app.core.deps import CurrentUser, DbSession

@router.get("/plans")
def list_plans(user: CurrentUser, db: DbSession): ...
```

要按权限挡人，再加一行：`Depends(require_permission("studyplan:add"))`。当前只有后台三处权限点真正生效，其余 13 个是数据，等业务模块挂上去。

## 四、目录

```
kaoyan-rbac/
├── backend/
│   ├── app/                 # 22 个 Python 文件
│   ├── sql/rbac_mysql.sql   # MySQL 8 建表脚本
│   ├── scripts/smoke_test.py# 端到端自测（60 项）
│   ├── requirements.txt
│   └── .env.example
├── frontend/src/            # 16 个前端文件
└── docs/改造说明.md          # 字段映射 / 扩展声明 / 迁移 / SMTP / 接口对照 / 验收
```
