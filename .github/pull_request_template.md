## 变更说明

<!-- 一句话说明这个 PR 做了什么, 以及为什么 -->

关联 Issue: closes #

## 变更类型

- [ ] ✨ feat 新功能
- [ ] 🐛 fix 缺陷修复
- [ ] ♻️ refactor 重构 (无行为变化)
- [ ] 📝 docs 文档
- [ ] ✅ test 测试
- [ ] 🏗️ build/ci 构建或流水线
- [ ] ⚡ perf 性能优化
- [ ] 🔧 chore 杂项

## 影响范围

- [ ] `apps/web` 前端
- [ ] `apps/api` 后端
- [ ] `infra/` / `docker-compose` 部署
- [ ] `.github/` CI
- [ ] 数据库结构变更 (迁移文件: <!-- 填写 alembic revision id -->)

## 自测清单

- [ ] 本地 `docker compose up -d --build` 可正常启动, 页面/接口可访问
- [ ] 后端: `cd apps/api && pytest` 通过
- [ ] 后端: 新增/修改接口已在 `/api/v1/docs` 验证
- [ ] 前端: `pnpm --filter @app/web type-check && pnpm --filter @app/web test` 通过
- [ ] 数据库变更有对应 alembic 迁移 (`alembic revision --autogenerate -m "..."`)
- [ ] 无密钥/口令等敏感信息被提交
- [ ] 已更新相关文档 (README / docs/)

## 接口变更 (如有)

| 方法 | 路径 | 说明 | 是否兼容 |
| ---- | ---- | ---- | -------- |
|      |      |      |          |

## 截图 / 录屏 (UI 变更必填)

<!-- 拖拽图片到此 -->

## 评审关注点

<!-- 希望 reviewer 重点看哪里? 有哪些已知取舍? -->
