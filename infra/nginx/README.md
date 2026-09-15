# 反向代理与 WebSocket 说明 (SG4)

本文件描述 **两层代理** 的拓扑、WebSocket 升级的必要配置, 以及推荐的生产部署形态。
`apps/web/nginx.conf`(位于前端镜像内, 由前端负责维护)负责第二层; 本目录只提供运维
视角的说明与示例片段。

---

## 1. 两层代理拓扑

```
                          第 1 层(生产: 可选但强烈建议)                第 2 层(已在镜像内)
浏览器 ──HTTPS──> 外层 nginx / 云 LB / CDN ──────HTTP──────> web 容器 nginx ──┬── 静态资源 / (try_files → index.html)
                  · TLS 终止                                              ├── /api/  ──> http://api:8000
                  · 真实域名 + 证书                                        └── /ws     ──> http://api:8000 (Upgrade)
                  · 限流 / 安全响应头
```

- **第 2 层**(`apps/web/nginx.conf`, 监听容器 80):
  - `/` → SPA 静态资源, 非文件路径回退到 `index.html`(支持前端路由刷新);
  - `/api/` → `proxy_pass http://api:8000;`(保留 `/api` 前缀, 后端路由本身就是 `/api/v1/...`);
  - `/ws` → `proxy_pass http://api:8000;` 且必须带 Upgrade 头。
- **第 1 层**(外层, 不在本仓库内): 只做 TLS、域名、限流与转发, 一般**不再改写路径**,
  把 `/`、`/api/`、`/ws` 原样交给 web 容器。

本机开发时通常没有第 1 层, 直接访问 `http://127.0.0.1:${WEB_PORT:-8080}` 即可;
不要用 `http://127.0.0.1:${API_PORT:-8000}` 打开前端 —— 那样前端请求会变成跨域。

---

## 2. WebSocket 升级要点(最容易出问题的地方)

`/ws` 路径既不经过 Vite 的 HMR, 也不走普通 HTTP 语义, 必须显式开启升级。第 2 层
nginx(前端维护)与第 1 层外层 nginx **都要**包含下面这组指令:

```nginx
location /ws {
    proxy_pass http://api:8000;      # 外层改为后端所在地址, 例如 http://127.0.0.1:8080
    proxy_http_version 1.1;          # ← WebSocket 必须 1.1, 不能是默认的 1.0

    proxy_set_header Upgrade    $http_upgrade;   # ← 关键: 透传 Upgrade
    proxy_set_header Connection "upgrade";       # ← 关键: 固定为 upgrade

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_read_timeout 3600s;        # ← 长连接不能被默认 60s 掐断
    proxy_send_timeout 3600s;
    proxy_buffering off;             # ← 实时消息不要缓冲
}
```

最常见的三个故障:

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 连接后立刻 400 / 426 | `proxy_http_version` 不是 `1.1`, 或缺 `Upgrade`/`Connection` | 按上面片段补齐 |
| 连接 60 秒后必断 | `proxy_read_timeout` 用默认值 | 调大到 3600s, 并让后端定时发 ping |
| 升级成功但握手 404 | `location` 用了 `location /ws/` 或路径被 rewrite | 用 `location /ws`(前缀匹配), 保持后端 `/ws` 前缀 |

其它注意点:

- **不要**在 `/ws` 的 location 上启用 `proxy_cache` 或 gzip 缓冲。
- 若上层还套了 CDN(Cloudflare 等), CDN 也必须开启 WebSocket 支持。
- 生产使用 `wss://` 时, 前端 `VITE_WS_BASE_URL` 仍写相对路径 `/ws`, 由浏览器按当前
  页面的协议自动取 `ws://` 或 `wss://` —— 这样最不容易出错。
- 扩容到多个 `api` 副本时, WebSocket 广播必须走 Redis pub/sub(本仓库已有
  `REDIS_URL`), 否则只有收到请求的那个副本会推送消息。

---

## 3. API 反代的补充设置

```nginx
location /api/ {
    proxy_pass http://api:8000;         # 结尾不带 / —— 保留 /api 前缀
    proxy_http_version 1.1;
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    client_max_body_size 50m;           # ← 附件上传, 与后端/存储限制保持一致
    proxy_read_timeout   120s;          # ← 导出等长耗时接口
}
```

要点:

- `proxy_set_header Host $host;` 会改变后端看到的 Host。若后端做**预签名 URL** 且
  依赖 Host, 请确认 `MINIO_PUBLIC_ENDPOINT` 与外部域名一致(见
  `infra/minio/README.md` 第 3 节)。
- 后端已经配置了 CORS(`CORS_ORIGINS`)。同源代理场景下前端请求不再跨域, 可以把
  `CORS_ORIGINS` 收紧到真实域名, 但**不要设成 `*`** 配合凭据使用。
- 安全响应头建议在外层统一下发:
  `Strict-Transport-Security`、`X-Content-Type-Options: nosniff`、
  `Referrer-Policy`、`X-Frame-Options: SAMEORIGIN`(或 CSP)。
- 上传大小要与后端限制、MinIO 单次 PUT 上限三者对齐, 否则会出现"前端失败但后端无日志"。

---

## 4. 推荐的生产拓扑

容器化 MySQL/Redis/MinIO 适合开发、演示和单机小规模部署。**真正上生产时建议把有状态
组件换成托管服务**, 只保留无状态容器:

| 组件 | 单机 Compose(本仓库) | 推荐生产形态 |
| --- | --- | --- |
| MySQL | `mysql:8.4` + 命名卷 | 云 RDS / 托管 MySQL 8.x(自动备份、主从、PITR) |
| Redis | `redis:7.4-alpine` + AOF | 云 Redis / Redis Sentinel / Cluster(高可用 + 密码 + TLS) |
| MinIO | `minio/minio` + 命名卷 | 云对象存储(OSS/COS/S3)或 Ceph 集群; 配合 CDN |
| api | 单容器 + uvicorn workers | 多副本 + 滚动发布(Compose/K8s/ECS), 由 LB 分发 |
| web | nginx 静态资源容器 | 同样多副本, 或直接把静态资源放 CDN/对象存储 |

切换方式: 只改 `.env`(`DATABASE_URL`、`REDIS_URL`、`MINIO_*`), 再把 compose 中对应的
`depends_on` 与基础设施服务移除即可, 业务代码无需改动。

生产检查清单:

1. `.env` 不进版本库; 密码用密钥管理服务注入, 且 `MYSQL_ROOT_PASSWORD`、
   `SECRET_KEY`、`MINIO_*` 全部重新生成, 不与示例相同。
2. `AUTO_CREATE_TABLES=0`, 表结构只由 alembic 迁移负责; `SEED_DEMO_DATA=0`。
3. 只有外层代理暴露 80/443; `MYSQL_PORT`、`REDIS_PORT`、`MINIO_CONSOLE_PORT`
   **不要**映射到公网(开发机上也尽量绑 `127.0.0.1`, 例如
   `"127.0.0.1:${MYSQL_PORT}:3306"`)。
4. 数据库与 Redis 走内网/私有子网, 开启 TLS 与密码, 限制来源安全组。
5. 备份: 数据库逻辑备份 + 对象存储版本控制; 命名卷不是备份方案。
6. 日志统一收集(compose 已配置 json-file 轮转), 并设置磁盘告警。
7. 定期 `docker compose pull` 更新基础镜像(尤其 nginx/redis/mysql/minio 的安全补丁),
   更新前先验证 `docker compose config`。
