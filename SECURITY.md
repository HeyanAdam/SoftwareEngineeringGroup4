# 安全策略 (Security Policy)

## 支持的版本

| 版本 | 安全更新 |
| --- | --- |
| `main` 最新提交 | ✅ |
| 已发布 tag (`v*`) 的最近一个小版本 | ✅ |
| 更早的历史版本 | ❌ |

## 报告漏洞

**请不要通过公开 Issue 报告安全问题。**

请使用 GitHub 的私密渠道: 仓库 -> **Security** -> **Report a vulnerability** (Security Advisories), 或直接联系维护者。

请在报告中包含:

- 漏洞类型与影响范围 (是否需要登录、需要的角色权限)
- 复现步骤或 PoC (最小化)
- 受影响版本/提交
- 如有可能, 给出修复建议
- 是否愿意被致谢

我们会在 **5 个工作日**内确认收到, 并在修复发布后公开致谢 (除非你要求匿名)。

## 安全基线 (本项目已实现)

- 口令使用 bcrypt 哈希, 登录失败次数限制 (Redis 计数)
- JWT access/refresh 双令牌; refresh 令牌一次性使用并旋转, 存 Redis 白名单; 改密/登出使 `token_version` 自增, 旧令牌立即失效
- 全部业务异常统一信封, 生产环境不再向客户端暴露堆栈
- CORS 白名单由 `CORS_ORIGINS` 控制; 生产环境默认关闭 `/docs`
- 上传文件有类型与体积白名单, 对象 key 使用 UUID (不可枚举)
- 下载走 MinIO 预签名 URL, 有效期可控
- 容器内以非 root 用户运行, 多阶段构建, 最小化运行时依赖
- CI 集成 gitleaks (密钥扫描)、Trivy (配置扫描)、dependency-review (依赖漏洞)

## 部署者须知 (务必逐条确认)

- [ ] 修改 `.env` 中所有 `*-change-me` 默认口令与 `SECRET_KEY`
- [ ] `SEED_DEMO_DATA=0` 并删除演示账号 `admin/Admin@123456`
- [ ] `APP_ENV=production` (此时 `SECRET_KEY` 含 `change-me` 会直接启动失败)
- [ ] `AUTO_CREATE_TABLES=0`, 表结构统一由 alembic 迁移管理
- [ ] 生产环境用托管 MySQL/Redis/对象存储, 或至少配置持久化卷与备份
- [ ] 前置网关开启 HTTPS, 并正确传递 `X-Forwarded-*` (后端已启用 `--proxy-headers`)
- [ ] 限制 MySQL/Redis/MinIO 端口不对公网暴露 (compose 中仅暴露 web 端口即可)
- [ ] 为 MinIO 桶设置最小权限策略, 不要把桶设为公开可写
