# apps/web · 前端应用

Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia + Vue Router + 原生 WebSocket。

完整说明见仓库根目录 [README.md](../../README.md)。

## 本机开发

```bash
# 仓库根目录
pnpm install
pnpm dev            # http://localhost:5173, 自动代理 /api 与 /ws 到 127.0.0.1:8000
```

后端未启动时页面可打开但接口报错, 先确保 `pnpm api:dev` 或 `pnpm up:infra` 已运行。

## 命令

| 命令 | 说明 |
| --- | --- |
| `pnpm --filter @app/web dev` | 开发服务器 (HMR) |
| `pnpm --filter @app/web build` | 类型检查 + 生产构建, 产物在 `dist/` |
| `pnpm --filter @app/web preview` | 预览构建产物 |
| `pnpm --filter @app/web type-check` | vue-tsc 类型检查 |
| `pnpm --filter @app/web test` | vitest 单元测试 |
| `pnpm --filter @app/web lint` | eslint 检查 |
| `pnpm --filter @app/web format` | prettier 格式化 |

## 关键约定

- **接口调用**: 一律通过 `src/api/*.ts`, 不要在组件里直接 `axios`。
- **错误处理**: 后端错误统一为 `{code, message, data}`, `src/utils/request.ts` 已统一弹 `ElMessage`; 需要分支时读 `code`。
- **令牌刷新**: 拦截器对 401 做单飞刷新并重放请求, 业务代码无需关心。
- **权限控制**: `v-permission="'users:write'"` 控制按钮; 路由 `meta.permissions` 控制页面; store 的 `hasPermission()` 用于逻辑判断。
- **类型契约**: 后端返回结构变化时, 同步更新 `src/types/`, 保证 `type-check` 通过。
- **ECharts**: 统一用 `components/charts/BaseChart.vue`, 按需引入图表类型, 避免整包体积。
- **样式**: SCSS + CSS 变量, 支持浅色/暗色; 不引入额外 UI 框架。

## 目录

```text
src/
├── api/          按模块的接口函数
├── components/   通用组件 (charts/common)
├── composables/  组合式函数 (useTable 等)
├── directives/   v-permission
├── layouts/      布局、侧边栏、顶栏
├── router/       路由表与全局守卫
├── stores/       Pinia: auth / app / ws / permission
├── types/        与后端契约一致的 TS 类型
├── utils/        request / ws / storage / format / permission
└── views/        页面 (dashboard / users / roles / files / chat / profile)
```

## 依赖与构建说明

- 构建链路为标准 Vite: TypeScript/SFC 由 Vite 内置 esbuild 转译, 生产构建用 esbuild 压缩,
  依赖预构建 (`optimizeDeps`) 保持开启。
- 开发服务器默认监听 `127.0.0.1:5173`, 可用环境变量覆盖:
  `VITE_DEV_HOST=0.0.0.0 VITE_DEV_PORT=5173 pnpm dev` (容器内开发需要 `0.0.0.0`)。
- 后端地址默认 `http://127.0.0.1:8000`, 需要指向别处时设置 `VITE_DEV_API_TARGET`。

