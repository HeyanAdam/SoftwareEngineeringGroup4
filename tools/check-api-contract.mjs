#!/usr/bin/env node
/**
 * 跨端接口契约校验
 *
 * 做两件事:
 *   1. 从后端 scan 出真实存在的路由(方法 + 路径)
 *   2. 从前端 src/api/*.ts 里提取所有调用(方法 + 路径), 逐条与后端比对
 *
 * 目的: 前后端由不同同学维护, 接口一改就容易两边脱节。
 *       提交前跑一次 `node tools/check-api-contract.mjs`, 能提前发现对不上的调用。
 *
 * 用法(仓库根目录):
 *   node tools/check-api-contract.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const BACKEND = join(ROOT, 'kaoyan-backend', 'app')
const FRONTEND_API = join(ROOT, 'kaoyan-frontend', 'src', 'api')
const FRONTEND_BASE = '/api' // 与 src/utils/request.ts 里的 baseURL 保持一致

const problems = []

// ---------------------------------------------------------------- 后端路由
function walk(dir, filter, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) walk(full, filter, out)
    else if (filter(full)) out.push(full)
  }
  return out
}

function backendRoutes() {
  const routes = new Set()
  for (const file of walk(BACKEND, (f) => f.endsWith('router.py'))) {
    const text = readFileSync(file, 'utf8')
    const prefix = text.match(/APIRouter\(\s*prefix\s*=\s*"([^"]*)"/)?.[1] ?? ''
    const re = /@router\.(get|post|put|patch|delete)\(\s*"([^"]*)"/g
    for (const [, method, path] of text.matchAll(re)) {
      routes.add(`${method.toUpperCase()} ${normalize(prefix + path)}`)
    }
  }
  // main.py 里直接挂在 app 上的接口
  const mainText = readFileSync(join(BACKEND, 'main.py'), 'utf8')
  for (const [, method, path] of mainText.matchAll(
    /@app\.(get|post|put|patch|delete)\(\s*"([^"]*)"/g,
  )) {
    routes.add(`${method.toUpperCase()} ${normalize(path)}`)
  }
  return routes
}

/** 把 {session_id} / {task_id} 统一成 {} 以便跨语言比对 */
function normalize(path) {
  const withBase = path.startsWith('/api') ? path : FRONTEND_BASE + path
  return withBase.replace(/\{[^}]+\}/g, '{}').replace(/\/+$/, '') || '/'
}

// ---------------------------------------------------------------- 前端调用
/** 前端调用写成 request.get<PlanDetail>(`/plan/plans/${planId}`) 这类形式 */
function frontendCalls() {
  const calls = []
  const re =
    /request\.(get|post|put|patch|delete)\s*(?:<[^>]*>)?\s*\(\s*(`[^`]*`|'[^']*'|"[^"]*")/g

  for (const file of walk(FRONTEND_API, (f) => f.endsWith('.ts'))) {
    const text = readFileSync(file, 'utf8')
    for (const [full, method, rawPath] of text.matchAll(re)) {
      // 模板字符串里的 ${xxx} 视为路径参数
      const path = rawPath.slice(1, -1).replace(/\$\{[^}]+\}/g, '{}')
      calls.push({
        file: file.replace(ROOT + '\\', '').replace(ROOT + '/', ''),
        method: method.toUpperCase(),
        path: normalize(path),
        raw: full.trim(),
      })
    }
  }
  return calls
}

// ---------------------------------------------------------------- 主流程
const routes = backendRoutes()
const calls = frontendCalls()

console.log(`后端路由: ${routes.size} 条`)
console.log(`前端调用: ${calls.length} 处`)

for (const call of calls) {
  const key = `${call.method} ${call.path}`
  if (!routes.has(key)) {
    problems.push(`${call.file}: 调用了后端不存在的接口 -> ${key}`)
  }
}

// 反向提示: 后端有但前端没用的接口(仅提示, 不算错误)
const used = new Set(calls.map((c) => `${c.method} ${c.path}`))
const unused = [...routes].filter(
  (r) => !used.has(r) && !r.endsWith('/ping') && r !== `GET ${FRONTEND_BASE}`,
)

if (problems.length) {
  console.log(`\n发现 ${problems.length} 个对不上的调用:`)
  for (const p of problems) console.log('  - ' + p)
  process.exit(1)
}

console.log('\n接口契约一致: 前端每一处调用都能在后端找到对应路由 ✅')
if (unused.length) {
  console.log(`\n提示: 以下后端接口前端尚未使用(共 ${unused.length} 条, 不含 /ping):`)
  for (const r of unused) console.log('  · ' + r)
}
