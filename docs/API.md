# 接口一览 (API Reference)

- 统一前缀: `{API_V1_PREFIX}` = `/api/v1`
- 交互式文档: `GET /api/v1/docs` (OpenAPI JSON: `/api/v1/openapi.json`), 生产环境默认关闭 (`ENABLE_DOCS=false`)
- 鉴权: `Authorization: Bearer <access_token>` (登录/注册/健康检查/刷新令牌除外)
- 时间: ISO 8601 UTC

## 统一响应约定

分页响应:

```json
{
  "items": [ { "id": 1 } ],
  "meta": { "page": 1, "page_size": 10, "total": 42, "pages": 5 }
}
```

错误响应 (`code` = HTTP 状态码 × 100 + 序号, 前端可据此做分支):

```json
{ "code": 40300, "message": "没有权限执行该操作", "data": null }
```

| code | HTTP | 含义 |
| --- | --- | --- |
| 40000 | 400 | 请求参数不合法 |
| 40100 / 40101 / 40102 / 40103 / 40105 / 40107 | 401 | 未登录 / access 过期 / 令牌无效 / 类型错误 / 凭证错误 / refresh 失效 |
| 40300 | 403 | 无权限 |
| 40400 | 404 | 资源不存在 |
| 40900 | 409 | 唯一约束或状态冲突 |
| 41300 | 413 | 文件过大 |
| 42200 | 422 | 参数校验失败 (`data` 为字段级错误数组) |
| 42900 | 429 | 触发限流 |
| 50000 / 50001 / 50200 | 5xx | 未捕获异常 / 数据库错误 / 对象存储错误 |

## 健康检查

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/health/live` | 存活探针 (进程内, 不查依赖) | — |
| GET | `/health/ready` | 就绪探针 (MySQL/Redis/MinIO 连通性 + WS 连接数) | — |
| GET | `/health/info` | 运行时信息 (版本/SHA/Python/平台/运行时长) | — |
| GET | `/metrics` | Prometheus 指标 (文本格式) | — |

## 认证 `/auth`

| 方法 | 路径 | 说明 | 限流 |
| --- | --- | --- | --- |
| POST | `/auth/register` | 注册 (默认分配 `viewer` 角色) | 20/分/IP |
| POST | `/auth/login` | 登录, body `{username, password}`, `username` 支持邮箱 | 30/分/IP |
| POST | `/auth/refresh` | 刷新令牌 (**一次性, 返回新 refresh**) | — |
| POST | `/auth/logout` | 登出 (token_version +1, 所有 refresh 失效) | — |
| GET | `/auth/me` | 当前用户 (含 `roles`/`permissions`) | — |
| PATCH | `/auth/me` | 更新个人资料 (`email/full_name/phone`) | — |
| POST | `/auth/change-password` | 改密 (改后需重新登录) | — |
| GET | `/auth/permissions` | 当前用户权限点列表 | — |

## 用户 `/users`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/users` | `users:read` | 分页: `page,page_size,keyword,is_active,role,sort_by` |
| GET | `/users/stats` | `users:read` | `{total,active,disabled,superusers}` |
| GET | `/users/roles/options` | `users:read` | 角色下拉选项 |
| GET | `/users/{id}` | `users:read` | 详情 |
| POST | `/users` | `users:write` + 超管 | 创建用户 (可指定 `roles`) |
| PATCH | `/users/{id}` | `users:write` + 超管 | 更新 (含 `roles`, 传 `null` 表示不改) |
| PUT | `/users/{id}/roles` | `users:write` + 超管 | 覆盖式分配角色 |
| POST | `/users/{id}/toggle-active` | `users:write` + 超管 | 启用/禁用 |
| POST | `/users/{id}/reset-password` | `users:write` + 超管 | 返回随机新口令一次 |
| DELETE | `/users/{id}` | `users:write` + 超管 | 删除 (不能删自己/最后一个超管) |

## 角色与权限 `/roles`

| 方法 | 路径 | 权限 | 说明 |
| --- | --- | --- | --- |
| GET | `/roles` | 登录 | 角色列表 (含权限点 code) |
| GET | `/roles/permissions` | 登录 | 权限点全量 (按模块分组用 `module` 字段) |
| POST | `/roles` | `roles:write` + 超管 | 创建角色 |
| PATCH | `/roles/{id}` | `roles:write` + 超管 | 更新名称/描述/权限点 |
| DELETE | `/roles/{id}` | `roles:write` + 超管 | 删除 (内置角色或被用户占用时拒绝) |

内置角色: `super_admin`(全部) / `admin` / `editor` / `analyst` / `viewer`。
内置权限点: `users:read|write|create|update|delete|assign-role`, `roles:read|write`, `files:read|upload|download|delete`, `dashboard:read`, `chat:read|write|broadcast`, `system:monitor`。

## 文件 `/files`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/files` | 分页: `page,page_size,category,keyword,only_mine`; 非管理员只能看到自己的文件 |
| GET | `/files/stats` | `{files, bytes}` |
| POST | `/files/upload` | multipart: `file` + `category`, 服务端中转上传 |
| POST | `/files/presign-upload` | body `{filename,content_type,category,size}` → `{upload_url,object_name,bucket,expires_in}` |
| POST | `/files/complete` | 直传完成后登记元数据 (会校验对象确实存在) |
| GET | `/files/{id}` | 详情 + 预签名下载 URL |
| GET | `/files/{id}/download` | 仅返回预签名 URL |
| DELETE | `/files/{id}` | `files:delete`; 非管理员只能删自己的 |

前端直传三步:

```ts
const { upload_url, object_name } = await api.presignUpload({ filename, content_type, category, size })
await fetch(upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': content_type } })
await api.completeUpload({ object_name, original_name: filename, content_type, size, category })
```

## 仪表盘 `/dashboard`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/dashboard/overview` | `days`(7~180, 默认 30), `refresh=true` 绕过缓存。返回 `stats[] / trend[] / categories[] / role_distribution[]` |
| POST | `/dashboard/cache/refresh` | 清理仪表盘缓存 |

ECharts 映射建议: `trend` → 折线图, `categories` → 柱状图, `role_distribution` → 环形图, `stats` → 指标卡。

## 聊天 / 通知 `/chat`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/chat/rooms` | 聊天室列表 |
| GET | `/chat/rooms/{code}/messages` | 历史消息, `limit`(≤200), `before_id` 游标 |
| GET | `/chat/online` | 本实例视角的在线连接与房间人数 |
| POST | `/chat/broadcast` | query: `title, content, level`; 向全站推送通知, 返回投递数 |

## WebSocket `/ws`

连接: `ws(s)://<host>/ws?token=<access_token>&room=lobby`。鉴权失败以 `1008` 关闭。

客户端 → 服务端:

```json
{ "type": "ping" }
{ "type": "join",  "room": "dev" }
{ "type": "leave", "room": "dev" }
{ "type": "chat",  "room": "dev", "content": "大家好" }
{ "type": "typing","room": "dev" }
```

服务端 → 客户端:

```json
{ "type": "pong",  "ts": 1710000000 }
{ "type": "welcome", "user": {"id":1,"username":"admin"}, "rooms": ["lobby","dev"] }
{ "type": "joined", "room": "dev" }
{ "type": "chat", "room": "dev", "message": { "id": 12, "sender_name": "admin", "kind": "text", "content": "大家好", "created_at": "2025-01-01T10:00:00Z" } }
{ "type": "presence", "room": "dev", "online": 3, "users": ["admin","editor"] }
{ "type": "notification", "level": "info", "title": "系统维护", "content": "22:00 起停机 10 分钟" }
{ "type": "error", "content": "消息内容不能为空" }
```

行为约定:

- 连接成功后先收到 `welcome`, 随后补发该房间最近 30 条历史消息。
- 心跳: 客户端每 20s 发 `ping`; 服务端空闲超时 = `2 × WS_HEARTBEAT_SECONDS` 时主动回 `pong` 探活。
- 单条消息 > `WS_MAX_MESSAGE_BYTES` 直接拒绝。
- 多实例部署时, 消息经 Redis `ws:broadcast` 频道跨实例投递, 同一用户重复登录会顶掉旧连接 (`4001`)。

## 调试示例

```bash
# 登录拿 token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123456"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 当前用户
curl -s http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"

# 仪表盘数据
curl -s "http://localhost:8000/api/v1/dashboard/overview?days=14&refresh=true" -H "Authorization: Bearer $TOKEN"

# WebSocket 快速验证 (需安装 websocat)
websocat "ws://localhost:8000/ws?token=$TOKEN&room=lobby"
```
