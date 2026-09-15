# =============================================================================
# apps/web 多阶段构建: node:22-alpine 构建 -> nginx:1.27-alpine 托管
# 构建: docker build -t sg4-web apps/web
# =============================================================================

# ------------------------------- 构建阶段 -------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

# 启用 corepack 以使用仓库声明的 pnpm 版本
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

# 先复制依赖清单, 最大化利用构建缓存
# 说明: 本镜像以 apps/web 为构建上下文, 看不到仓库根的 pnpm-lock.yaml,
#       因此这里不使用 --frozen-lockfile (CI 会对根 lockfile 做一致性校验)。
COPY package.json ./
RUN pnpm install --no-frozen-lockfile

# 复制源码并构建; package.json 的 build 脚本会先跑 vue-tsc 类型检查再 vite 构建
COPY . .
RUN pnpm build

# ------------------------------- 运行阶段 -------------------------------
FROM nginx:1.27-alpine AS runner

# 站点配置 (SPA history 回退 + /api + /ws 反向代理)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 静态产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
