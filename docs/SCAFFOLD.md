# 脚手架使用说明

> **先读这一句**：仓库当前处于**脚手架阶段**。目录分层、约定、前后端连通链路已经搭好；
> 里面的「注册登录 / AI 问答 / 学习计划」是**照葫芦画瓢用的参考示例**，不是最终产品形态。
> 每个人开发的模块，请照着本文的步骤和示例来加。

## 目录

- [1. 脚手架提供了什么](#1-脚手架提供了什么)
- [2. 跑起来](#2-跑起来)
- [3. 必须先理解的 5 条约定](#3-必须先理解的-5-条约定)
- [4. 后端：新增一个模块（完整步骤）](#4-后端新增一个模块完整步骤)
- [5. 前端：新增一个页面模块（完整步骤）](#5-前端新增一个页面模块完整步骤)
- [6. 参考示例 vs 基础设施](#6-参考示例-vs-基础设施)
- [7. 提交前的自检](#7-提交前的自检)
- [8. 常见坑](#8-常见坑)

---

## 1. 脚手架提供了什么

| 能力 | 位置 | 状态 |
| --- | --- | --- |
| 后端分层骨架 | `kaoyan-backend/app/{core,models,schemas,services,modules}` | ✅ 约定已定 |
| 数据库连接（懒加载 + 启动建表） | `kaoyan-backend/app/core/database.py` | ✅ |
| 统一配置（读 `.env`） | `kaoyan-backend/app/core/config.py` | ✅ |
| 统一错误响应 `{code,message,data}` | `kaoyan-backend/app/core/exceptions.py` | ✅ |
| 登录鉴权（argon2 + JWT） | `core/security.py`、`core/deps.py` | ✅ |
| 前端工程化（Vite + TS + Element Plus + ECharts + axios） | `kaoyan-frontend/` | ✅ |
| 请求封装（自动带 token / 统一报错 / 401 退出） | `kaoyan-frontend/src/utils/request.ts` | ✅ |
| 路由 + 登录守卫 + 布局 + 菜单 | `src/router/`、`src/layouts/DefaultLayout.vue` | ✅ |
| 基础设施一键启动（MySQL/Redis/MinIO） | `docker-compose.yml` | ✅ |
| 三个模块的完整示例 | `modules/{user,ai_chat,study_plan}` | ⚠️ **参考示例** |
| 测试 / CI / 部署流水线 | — | ❌ 还没有，属于下一阶段 |

## 2. 跑起来

```bash
# 1. 基础设施
docker compose up -d                    # MySQL 3307 / Redis 6379 / MinIO 9000-9001

# 2. 后端（新终端）
cd kaoyan-backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env                  # 默认值已和 compose 对齐，不用改
uvicorn app.main:app --reload --port 8001
# 打开 http://127.0.0.1:8001/docs 应看到接口文档

# 3. 前端（再开一个终端）
cd kaoyan-frontend
npm install
npm run dev                             # http://localhost:5173
```

验证链路是否通：打开前端 → 注册一个账号 → 登录 → 左上角能看到昵称，就说明**前端 → 代理 → 后端 → MySQL** 整条链路是通的。

## 3. 必须先理解的 5 条约定

**① 响应格式**
成功时后端**直接返回数据本身**，不包 `{code, data}` 外壳；出错时才是 `{code, message, data}`。
前端的 `request.ts` 已经处理好：成功直接拿到数据，失败自动弹 `message` 并抛 `RequestError`。

**② 前端不写后端地址**
一律 `import { request } from '@/utils/request'`，路径写 `/模块名/xxx`（不要带 `/api`，不要写 `127.0.0.1:8001`）。
开发环境的 `/api → 8001` 代理在 `vite.config.ts` 里。

**③ 后端分层单向依赖**
```
modules/*/router.py  →  services/  →  models/ 、 core/
     （参数校验）        （业务逻辑）     （表结构）（基础设施）
```
- router 里**不写 SQL、不写复杂分支**，只做参数校验 + 调 service
- service 里**不依赖 FastAPI 的 Request/Response**，方便以后写单元测试
- `core/` 不依赖任何业务模块

**④ 需要登录的接口，加一个依赖就行**
```python
from app.core.deps import CurrentUser, DbSession

@router.get("/xxx")
def my_api(user: CurrentUser, db: DbSession):
    ...  # user 就是当前登录用户，未登录会自动返回 401
```

**⑤ 新增页面要同时改两处**
`src/views/` 里建页面文件 + `src/router/routes.ts` 里注册路由（需要登录就加 `meta.requiresAuth: true`），
菜单项在 `src/layouts/DefaultLayout.vue` 里加。

---

## 4. 后端：新增一个模块（完整步骤）

假设要做一个**错题本**模块（`mistake`），提供「新建错题 / 我的错题列表」。

### 步骤 1：定义表（`app/models/mistake.py`）

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Mistake(Base):
    __tablename__ = "mistakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, comment="错因分析")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
```

然后在 `app/models/__init__.py` 里导出 —— **这一步不能忘，否则不会建表**：

```python
from app.models.mistake import Mistake
__all__ = [..., "Mistake"]
```

> 建表方式：启动时 `Base.metadata.create_all()` 自动创建（`AUTO_CREATE_TABLES=1`，开发期够用）。
> 表结构稳定后要改成 Alembic 迁移（`alembic` 已经在 requirements 里），这属于后续阶段的工作。

### 步骤 2：定义出入参（`app/schemas/mistake.py`）

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MistakeCreateRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=50)
    question: str = Field(min_length=1, max_length=2000)
    reason: str | None = Field(default=None, max_length=1000)


class MistakeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # 允许直接吃 ORM 对象

    id: int
    subject: str
    question: str
    reason: str | None = None
    created_at: datetime
```

### 步骤 3：写业务逻辑（`app/services/mistake_service.py`）

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.mistake import Mistake


class MistakeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_mine(self, user_id: int) -> list[Mistake]:
        stmt = (
            select(Mistake)
            .where(Mistake.user_id == user_id)
            .order_by(Mistake.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, user_id: int, *, subject: str, question: str, reason: str | None) -> Mistake:
        item = Mistake(user_id=user_id, subject=subject, question=question, reason=reason)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, mistake_id: int, user_id: int) -> None:
        item = self.db.get(Mistake, mistake_id)
        # 他人的数据与不存在返回同样的 404，不泄露「这条记录是否存在」
        if item is None or item.user_id != user_id:
            raise NotFoundError("错题不存在")
        self.db.delete(item)
        self.db.commit()
```

### 步骤 4：写路由（`app/modules/mistake/router.py`）

先建目录和空文件：`app/modules/mistake/__init__.py`、`router.py`

```python
from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.mistake import MistakeCreateRequest, MistakeOut
from app.services.mistake_service import MistakeService

router = APIRouter(prefix="/api/mistake", tags=["错题本模块"])


@router.get("/list", response_model=list[MistakeOut], summary="我的错题")
def list_mistakes(user: CurrentUser, db: DbSession) -> list[MistakeOut]:
    items = MistakeService(db).list_mine(user.id)
    return [MistakeOut.model_validate(item) for item in items]


@router.post("/create", response_model=MistakeOut, status_code=status.HTTP_201_CREATED,
             summary="录入错题")
def create_mistake(payload: MistakeCreateRequest, user: CurrentUser, db: DbSession) -> MistakeOut:
    item = MistakeService(db).create(
        user.id, subject=payload.subject, question=payload.question, reason=payload.reason
    )
    return MistakeOut.model_validate(item)
```

### 步骤 5：注册路由（`app/main.py`）

```python
from app.modules.mistake.router import router as mistake_router
...
app.include_router(mistake_router)
```

### 步骤 6：验证

重启后端 → 打开 http://127.0.0.1:8001/docs → 在 Swagger 里点 `Authorize` 填 token → 直接调接口。
**不用等前端做完就能自测**，这是 FastAPI 文档最大的好处。

---

## 5. 前端：新增一个页面模块（完整步骤）

继续用错题本举例。

### 步骤 1：定义类型（`src/types/mistake.ts`）

```ts
export interface Mistake {
  id: number
  subject: string
  question: string
  reason: string | null
  created_at: string
}

export interface MistakeCreatePayload {
  subject: string
  question: string
  reason?: string
}
```

### 步骤 2：封装接口（`src/api/mistake.ts`）

照着 `src/api/plan.ts` 写，注意**路径不带 `/api`**（baseURL 已经带了）：

```ts
import { request } from '@/utils/request'
import type { Mistake, MistakeCreatePayload } from '@/types/mistake'

export function listMistakes(): Promise<Mistake[]> {
  return request.get<Mistake[]>('/mistake/list')
}

export function createMistake(payload: MistakeCreatePayload): Promise<Mistake> {
  return request.post<Mistake>('/mistake/create', payload)
}
```

### 步骤 3：写页面（`src/views/MistakeView.vue`）

```vue
<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-header">
        <span>我的错题本</span>
        <el-button type="primary" :loading="submitting" @click="handleCreate">录入错题</el-button>
      </div>
    </template>

    <el-table :data="items" :loading="loading" empty-text="还没有错题">
      <el-table-column prop="subject" label="科目" width="120" />
      <el-table-column prop="question" label="题目" min-width="240" show-overflow-tooltip />
      <el-table-column prop="reason" label="错因" min-width="180" show-overflow-tooltip />
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createMistake, listMistakes } from '@/api/mistake'
import type { Mistake } from '@/types/mistake'

const items = ref<Mistake[]>([])
const loading = ref(false)
const submitting = ref(false)

async function load(): Promise<void> {
  loading.value = true
  try {
    items.value = await listMistakes()
  } catch {
    // 错误提示已由 request.ts 统一处理
  } finally {
    loading.value = false
  }
}

async function handleCreate(): Promise<void> {
  submitting.value = true
  try {
    // 真实项目里这里应弹表单，示例从简
    await createMistake({ subject: '数学', question: '示例题目', reason: '计算失误' })
    ElMessage.success('已录入')
    await load()
  } catch {
    /* 同上 */
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>
```

### 步骤 4：注册路由（`src/router/routes.ts`）

在 `DefaultLayout` 的 `children` 里加一项：

```ts
{
  path: 'mistakes',
  name: 'mistakes',
  component: () => import('@/views/MistakeView.vue'),
  meta: { title: '错题本', requiresAuth: true },
},
```

### 步骤 5：加菜单（`src/layouts/DefaultLayout.vue`）

照着已有 `el-menu-item` 复制一项，`index` 写路由路径 `/mistakes`，图标从 `@element-plus/icons-vue` 里选；
**如果用新图标，记得在 `src/main.ts` 的 `icons` 对象里登记**，否则模板里 `<新图标 />` 是空白的。

### 步骤 6：验证

```bash
npm run dev          # 打开 http://localhost:5173/mistakes
npm run type-check   # 类型检查（提交前必跑）
```

---

## 6. 参考示例 vs 基础设施

后面接手开发时，请分清这两类文件：

### 🟢 基础设施（约定，尽量保持一致，不要随意改）

| 文件 | 作用 |
| --- | --- |
| `backend/app/core/*` | 配置、数据库、鉴权、异常、依赖注入 |
| `backend/app/main.py` | 应用装配与路由注册 |
| `backend/app/models/__init__.py` | 模型导出（漏了就建不了表） |
| `frontend/src/utils/request.ts` | axios 封装 |
| `frontend/src/router/index.ts` | 路由守卫 |
| `frontend/src/layouts/DefaultLayout.vue` | 全局布局与菜单 |
| `frontend/vite.config.ts`、`tsconfig*.json` | 工程化配置 |
| `docker-compose.yml` | 基础设施编排 |

### 🟡 参考示例（可以改、可以删、可以照着抄）

| 文件 | 说明 |
| --- | --- |
| `backend/app/modules/user/*`、`schemas/user.py`、`models/user.py` | 注册登录示例（**登录鉴权建议保留，其它模块都依赖它**） |
| `backend/app/modules/ai_chat/*`、`services/chat_service.py`、`models/chat.py` | 会话与消息示例；AI 回答目前是关键词规则，将来接 RAG 时替换 `generate_answer()` 即可 |
| `backend/app/modules/study_plan/*`、`services/plan_service.py`、`models/plan.py` | 计划与任务示例，含「创建时自动拆解每日任务」的写法 |
| `frontend/src/views/*` | 各页面示例：表格 + 分页 + 弹窗表单 + ECharts 的典型写法都在里面 |
| `tools/*` | 自检脚本，可按需保留或删除 |

**判断标准**：如果你要做的功能与某个示例结构相似（比如「列表 + 新增 + 删除」），直接复制那个模块改名字最快。

## 7. 提交前的自检

```bash
# 仓库根目录
node tools/check-api-contract.mjs      # 前端调的接口后端都有吗
node tools/check-frontend-static.mjs   # import 路径 / 类型引用 / 硬编码检查
python tools/check-python-names.py     # 后端拼写错误与漏 import

# 前端目录
cd kaoyan-frontend && npm run type-check && npm run build

# 后端目录
cd kaoyan-backend && python tools/check_backend_consistency.py
```

## 8. 常见坑

| 现象 | 原因 / 解决 |
| --- | --- |
| 新表没建出来 | 忘了在 `app/models/__init__.py` 导出模型 |
| 接口一直 401 | 需要登录的接口必须加 `user: CurrentUser` 依赖；Swagger 里要先点 Authorize |
| 前端请求 404 | `request.get('/mistake/list')` 路径少写/多写了 `/api`；或后端没重启 |
| 前端拿到的类型不对 | 后端改了字段，忘了同步改 `src/types/*.ts` |
| 模板里图标不显示 | 新图标没在 `src/main.ts` 的 `icons` 里注册 |
| 新页面点菜单空白 | 只建了 `views/` 文件，忘了在 `router/routes.ts` 注册 |
| 改了 `.env` 没生效 | 后端要重启进程；`.env` 不提交，改完记得同步 `.env.example` |
| 连不上数据库 | `DB_PORT` 必须是 **3307**（compose 映射到宿主机 3307，不是 3306） |
| 多人同时改同一文件冲突 | 每人只改自己模块的目录；`main.py`、`routes.ts`、`DefaultLayout.vue` 这类共享文件改动要小、改动后及时 push |
