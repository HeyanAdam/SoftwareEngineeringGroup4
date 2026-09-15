# MinIO 对象存储运维说明 (SG4)

本目录说明本仓库 MinIO 容器的使用方式、**浏览器可达的预签名 URL** 这一最容易踩坑的点,
以及生产环境的替代方案。

---

## 1. 容器与端口

`docker-compose.yml` 中的 `minio` 服务:

| 项 | 值 |
| --- | --- |
| 镜像 | `minio/minio:latest` |
| 数据目录 | `/data` → 命名卷 `${COMPOSE_PROJECT_NAME}_minio_data` |
| S3 API | 容器内 `9000` → 宿主机 `${MINIO_API_PORT:-9000}` |
| Web 控制台 | 容器内 `9001` → 宿主机 `${MINIO_CONSOLE_PORT:-9001}` |
| 健康检查 | `mc ready local`(镜像自带 `mc`, 无需凭据) |
| 根凭据 | `${MINIO_ROOT_USER}` / `${MINIO_ROOT_PASSWORD}` |

控制台地址:`http://127.0.0.1:${MINIO_CONSOLE_PORT:-9001}`
(浏览器里如果用 `localhost` 登录失败, 换成 `127.0.0.1` 再试 —— 只影响控制台 cookie, 与 API 无关。)

`createbuckets` 是**一次性任务**: 等 `minio` 健康后创建 `${MINIO_BUCKET}`、设置
`download`(匿名只读)策略, 然后退出。查看结果:

```powershell
docker compose logs createbuckets          # 应看到 "完成: sg4-files"
docker compose ps -a                       # createbuckets 状态应为 Exited (0)
```

若业务要求"所有文件访问都必须经过预签名 URL", 请删除 `docker-compose.yml` 中
`mc anonymous set download ...` 那一行, 让桶保持**私有**(默认行为)。

---

## 2. 手工创建桶

### 方式 A: Web 控制台

1. 打开 `http://127.0.0.1:9001`, 用 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` 登录。
2. 左侧 **Buckets → Create Bucket**, 名称填写 `${MINIO_BUCKET}`(例如 `sg4-files`)。
3. (可选)在 **Anonymous** 规则里添加前缀 `*` 的 `readonly` 访问, 等价于
   `mc anonymous set download`。
4. 需要给后端单独开一个"最小权限"账号时, 到 **Identity → Users** 创建用户, 再到
   **Identity → Policies / Bucket Access** 授予该桶读写权限, 然后把这个用户的
   Access/Secret Key 写进 `.env` 的 `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY`
   (注意: `.env.example` 里这两项默认与 root 账号相同, 生产务必分离)。

### 方式 B: `mc` 命令行(容器外)

```powershell
# 用一次性容器执行, 避免本机安装 mc
docker run --rm -it --network sg4_app_net minio/mc:latest `
  mc alias set local http://minio:9000 <MINIO_ROOT_USER> <MINIO_ROOT_PASSWORD>

docker run --rm --network sg4_app_net minio/mc:latest mc mb --ignore-existing local/sg4-files
docker run --rm --network sg4_app_net minio/mc:latest mc anonymous set download local/sg4-files
docker run --rm --network sg4_app_net minio/mc:latest mc ls local
```

在宿主机已有 `mc` 且端口已映射时, 也可以直接用宿主机地址:

```powershell
mc alias set sg4 http://127.0.0.1:9000 <MINIO_ROOT_USER> <MINIO_ROOT_PASSWORD>
mc mb --ignore-existing sg4/sg4-files
mc ls sg4
```

### 方式 C: 重新触发自动创建

```powershell
docker compose up -d --force-recreate createbuckets
```

---

## 3. 预签名 URL 必须"浏览器可达"(最常见的坑)

后端用 `MINIO_ENDPOINT` **在容器内**读写对象, 但它生成预签名 URL 时使用的 host 必须是
**浏览器能解析到的地址**, 两者往往不同:

| 变量 | 取值 | 谁在用 |
| --- | --- | --- |
| `MINIO_ENDPOINT` | `minio:9000`(容器网络内服务名) | 后端进程 ↔ MinIO 的 S3 调用 |
| `MINIO_PUBLIC_ENDPOINT` | `127.0.0.1:9000`(宿主机映射端口) | 浏览器直接下载/预览 |

要点:

1. `MINIO_PUBLIC_ENDPOINT` 的 host:port 必须与 compose 的
   `"${MINIO_API_PORT}:9000"` 映射**一致**, 否则签名里的 Host 与浏览器请求的 Host
   不匹配, MinIO 会返回 `SignatureDoesNotMatch`。
2. **不要**用 `localhost:9000` 作为 `MINIO_PUBLIC_ENDPOINT` 的默认值去做容器间通信;
   `localhost` 在容器里指向容器自身。
3. 签名还包含 `Host` 与过期时间, 因此:
   - 反向代理必须**原样转发 Host**(`proxy_set_header Host $host;`),
     且不能改写路径前缀, 否则 URL 失效;
   - 代理层若做 URL 重写(例如 `/files/xxx` → `/sg4-files/xxx`), 必须让签名也按
     外部路径生成, 或者干脆让后端生成相对路径由前端拼接。
4. 若通过 HTTPS 对外提供服务, 需设置 `MINIO_SECURE=true`, 并确保
   `MINIO_PUBLIC_ENDPOINT` 不带 `http://` 前缀、只写 `host:port`(端口为 443 时通常
   仍需显式写出, 具体以项目 `storage` 模块实现为准)。
5. 局域网/他人协作时, `127.0.0.1` 只对本机有效; 请改成宿主机局域网 IP 或域名, 并在
   `.env` 中同步修改, 然后 `docker compose up -d --force-recreate api`。

自检(浏览器或 curl):

```powershell
# 1) 直链是否可读(仅当桶策略为 download 时有意义)
curl.exe -I http://127.0.0.1:9000/sg4-files/<object-key>

# 2) 预签名 URL 是否可用: 从后端接口拿到 url 后原样 curl, 应返回 200 而不是 403
curl.exe -I "<presigned-url>"
```

---

## 4. 生产环境的反向代理考量

生产不建议把 MinIO 的 9000/9001 直接暴露到公网, 而是走统一入口:

```
浏览器 ──HTTPS──> 外层 nginx / 负载均衡 / CDN
                   ├── /            -> web 容器 (前端静态资源)
                   ├── /api/, /ws   -> api 容器
                   └── /files/      -> minio:9000 (或云对象存储)
```

注意事项:

- **Host 透传**: 预签名 URL 的 Host 参与签名, 代理必须保留原始 `Host`
  (`proxy_set_header Host $host;`), 必要时用 `proxy_set_header X-Forwarded-Host`。
- **大文件**: 上传/下载请关闭代理缓冲 (`proxy_request_buffering off;`
  `proxy_buffering off;`) 并放宽 `client_max_body_size` 与 `proxy_read_timeout`。
- **路径**: 建议 `/files/` 直接映射到桶根, 且不要在前缀被剥离后再去校验签名。
- **TLS**: HTTPS 终止在代理层时, 后端对外仍应生成 https 链接, 需保证
  `MINIO_SECURE=true` 且 `MINIO_PUBLIC_ENDPOINT` 使用外部域名(如 `files.example.com`)。
- **CORS**: 若前端用 `fetch` 直读对象, 需要给桶设置 CORS 规则
  (`mc cors set` 或在控制台配置 `AllowedOrigin` 为前端域名)。
- **更省心的替代**: 生产直接使用云对象存储(阿里云 OSS / 腾讯云 COS / AWS S3 /
  自建 Ceph RGW), 只要保持 S3 兼容, 业务代码通常只需改 endpoint 与凭据; 同时用 CDN
  加速下载并隐藏源站。

---

## 5. 常用运维命令

```powershell
docker compose logs -f minio                                   # 看日志
docker compose exec minio mc admin info local                   # 集群/容量信息
docker compose exec minio mc du local/sg4-files                 # 桶占用
docker compose down                                             # 停容器, 保留数据
docker compose down -v                                          # ⚠️ 连命名卷一起删, 数据全丢
```
