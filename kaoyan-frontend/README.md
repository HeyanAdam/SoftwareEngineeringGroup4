# kaoyan-frontend · 考研 AI 导学平台前端

Vue 3 + TypeScript + Vite + Pinia + Vue Router + Element Plus + ECharts。

## 环境要求

| 工具 | 版本 |
| --- | --- |
| Node.js | **22.18+ 或 24.12+**（`package.json` 的 `engines` 与 `@tsconfig/node24` 要求；不建议用 20 及以下） |
| npm | 随 Node 自带（10+） |

## 快速开始

```bash
npm install
npm run dev        # http://localhost:5173
```

> **首次拉取后务必先执行 `npm install`**：`package.json` 新增了 element-plus、echarts、axios、sass，
> 但 `package-lock.json` 尚未同步（新增依赖是在离线环境加入的），所以此时 `npm ci` 会失败、直接 `npm install` 即可刷新 lockfile。

开发服务器会把 `/api` 代理到后端 `http://127.0.0.1:8001`（见 `vite.config.ts`），所以**不需要**在前端代码里写后端地址，也不会有跨域问题。启动前端前请先按根目录 README 启动后端。

## 可用命令

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动开发服务器（HMR） |
| `npm run build` | 类型检查 + 生产构建，产物在 `dist/` |
| `npm run preview` | 预览构建产物 |
| `npm run type-check` | 仅做类型检查（vue-tsc） |
| `npm run lint` | oxlint + eslint 自动修复 |
| `npm run format` | prettier 格式化 `src/` |

## 目录结构

```text
src/
├── api/            接口封装，按后端模块划分
│   ├── auth.ts     注册 / 登录 / 个人信息
│   ├── chat.ts     AI 会话与消息
│   ├── plan.ts     学习计划与任务
│   └── index.ts    统一出口（authApi / chatApi / planApi）
├── layouts/
│   └── DefaultLayout.vue   左侧菜单 + 顶部栏 + <router-view>
├── router/
│   ├── index.ts    路由实例与登录守卫
│   └── routes.ts   路由表
├── stores/
│   └── auth.ts     token 与用户信息（持久化到 localStorage）
├── types/          与后端契约一致的 TS 类型
│   ├── api.ts      RequestError 等通用类型
│   ├── user.ts  chat.ts  plan.ts
├── utils/
│   └── request.ts  axios 实例：自动带 token、统一错误提示、401 退出登录
└── views/
    ├── LoginView.vue  RegisterView.vue
    ├── HomeView.vue       首页：统计卡片 + ECharts 图表
    ├── ChatView.vue       AI 问答
    ├── PlanView.vue       学习计划（含任务展开）
    ├── ProfileView.vue    个人中心
    └── NotFoundView.vue   404
```

## 约定

- **接口调用**：一律通过 `src/api/*`，不要在组件里直接 `axios`。
- **后端地址**：只使用 `baseURL: '/api'` + Vite 代理，禁止硬编码 `http://127.0.0.1:8001`。
- **响应格式**：成功时后端直接返回数据；失败时是 `{code, message, data}`，`utils/request.ts` 已经统一弹出 `message`，业务代码只需处理成功分支。
- **登录态**：token 存在 `localStorage` 的 `kaoyan_token`（`utils/request.ts` 与 `stores/auth.ts` 用同一个键）；401 时自动清除并跳回登录页。
- **路由守卫**：`meta.requiresAuth` 标记需要登录的页面，守卫只做同步的 token 判断，不阻塞导航。
- **Element Plus**：全量引入（`main.ts` 里 `app.use(ElementPlus, { locale: zhCn })`），图标按需具名注册后可在模板中直接以 `<HomeFilled />` 形式使用；新增图标记得在 `main.ts` 的 `icons` 里登记。
- **ECharts**：按需引入（`echarts/core` + 需要的图表与组件），容器需在 `onBeforeUnmount` 里 `dispose()`。

## 常见问题

| 问题 | 处理 |
| --- | --- |
| 接口全部 404 | 后端没启动，或没跑在 8001 端口；确认 `vite.config.ts` 里代理的 target |
| 打开页面一直跳登录页 | `localStorage` 里的 token 已过期，重新登录即可 |
| `npm install` 报 ERESOLVE | 项目内 `eslint-plugin-oxlint` 与 `oxlint` 版本有 peer 警告（不影响运行）；必要时加 `--legacy-peer-deps` |
| 类型检查报 Element Plus 属性错误 | 确认 `element-plus` 已安装且版本 ≥ 2.9 |
| 安装很慢 | 换源：`npm config set registry https://registry.npmmirror.com` |
