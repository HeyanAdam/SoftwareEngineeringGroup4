#!/usr/bin/env node
/**
 * 前端静态自查(离线环境替代 vue-tsc)
 *
 * 检查项:
 *   1. 每个 .ts/.vue 里的 import 路径都能解析到真实文件(含 @/ 别名与扩展名补全)
 *   2. 从本地模块导入的名字, 在目标文件里确实有导出
 *   3. 模板里用到的 PascalCase 组件, 在脚本里已导入/定义, 或属于 Element Plus / 全局注册图标
 *   4. 没有硬编码后端地址、没有 any / @ts-ignore、没有 /api/hello 残留
 *   5. SFC 结构完整: <template> 与 <script setup> 成对
 *
 * 用法(仓库根目录): node tools/check-frontend-static.mjs
 */

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const SRC = join(ROOT, 'kaoyan-frontend', 'src')
/** main.ts 里 app.component() 全局注册的图标, 模板中可直接使用 */
const MAIN_FILE = join(SRC, 'main.ts')
const VUE_BUILTINS = new Set(['RouterLink', 'RouterView', 'Transition', 'TransitionGroup', 'KeepAlive', 'Teleport', 'Suspense', 'Component'])

const problems = []
const files = []
const exportsByFile = new Map()

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) walk(full)
    else if (/\.(ts|vue)$/.test(full)) files.push(full)
  }
}
walk(SRC)

const rel = (p) => relative(ROOT, p).replace(/\\/g, '/')

/** 把 '@/' 或相对路径解析成真实文件 */
function resolveImport(spec, fromFile) {
  let base
  if (spec.startsWith('@/')) base = join(SRC, spec.slice(2))
  else if (spec.startsWith('.')) base = resolve(dirname(fromFile), spec)
  else return { external: true }

  for (const candidate of [
    base,
    `${base}.ts`,
    `${base}.vue`,
    `${base}.d.ts`,
    join(base, 'index.ts'),
    join(base, 'index.vue'),
  ]) {
    if (existsSync(candidate) && statSync(candidate).isFile()) return { file: candidate }
  }
  return { missing: base }
}

/** 提取一个文件导出的名字(含 export * as ns / export * from) */
function collectExports(text) {
  const names = new Set()
  for (const m of text.matchAll(
    /export\s+(?:async\s+)?(?:function|const|let|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/g,
  )) {
    names.add(m[1])
  }
  // export * as ns from './x'
  for (const m of text.matchAll(/export\s+\*\s+as\s+([A-Za-z_$][\w$]*)\s+from/g)) {
    names.add(m[1])
  }
  // export { a, b as c }
  for (const m of text.matchAll(/export\s*\{([^}]*)\}/g)) {
    for (const part of m[1].split(',')) {
      const piece = part.trim().replace(/^type\s+/, '')
      if (!piece) continue
      const asMatch = piece.match(/\s+as\s+([A-Za-z_$][\w$]*)$/)
      names.add(asMatch ? asMatch[1] : piece.split(/\s+/)[0])
    }
  }
  if (/export\s+default/.test(text)) names.add('default')
  return names
}

/** 从 import 语句里抽出所有被引入的本地名字 */
function importedLocalNames(script) {
  const names = new Set()
  const re =
    /import\s+(?:type\s+)?(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*['"]([^'"]+)['"]/g
  for (const m of script.matchAll(re)) {
    if (m[1]) names.add(m[1])
    if (m[2]) {
      for (const raw of m[2].split(',')) {
        const piece = raw.trim().replace(/^type\s+/, '')
        if (!piece) continue
        const asMatch = piece.match(/\s+as\s+([\w$]+)$/)
        names.add(asMatch ? asMatch[1] : piece.split(/\s+/)[0])
      }
    }
  }
  // 脚本内定义的组件(如 const Foo = defineComponent(...))
  for (const d of script.matchAll(/(?:const|function)\s+([A-Z][\w$]*)/g)) names.add(d[1])
  return names
}

// ---------- 全局注册的图标名 ----------
const globallyRegistered = new Set()
if (existsSync(MAIN_FILE)) {
  const mainText = readFileSync(MAIN_FILE, 'utf8')
  const block = mainText.match(/const icons[^=]*=\s*\{([\s\S]*?)\}/)
  if (block) {
    for (const m of block[1].matchAll(/([A-Za-z_$][\w$]*)\s*,?/g)) {
      if (m[1]) globallyRegistered.add(m[1])
    }
  }
}

// ---------- 第一遍: 收集导出 ----------
for (const file of files) {
  exportsByFile.set(file, collectExports(readFileSync(file, 'utf8')))
}

// ---------- 第二遍: 逐文件检查 ----------
let importCount = 0
let symbolChecks = 0

for (const file of files) {
  const text = readFileSync(file, 'utf8')
  const short = rel(file)
  const isVue = file.endsWith('.vue')

  // 1 + 2: import 解析与符号核对
  const importRe =
    /import\s+(?:type\s+)?(?:([\w$]+)\s*,?\s*)?(?:\{([^}]*)\})?\s*from\s*['"]([^'"]+)['"]/g
  for (const m of text.matchAll(importRe)) {
    const [, defaultName, namedBlock, spec] = m
    importCount++
    const resolved = resolveImport(spec, file)
    if (resolved.missing) {
      problems.push(`${short}: import 路径不存在 -> ${spec}`)
      continue
    }
    if (resolved.external) continue

    const targetExports = exportsByFile.get(resolved.file)
    if (!targetExports) continue

    // .vue 单文件组件天然有默认导出, 无需在源码里出现 export default 字样
    const targetIsVue = resolved.file.endsWith('.vue')
    if (defaultName && !targetIsVue && !targetExports.has('default')) {
      problems.push(`${short}: ${spec} 没有默认导出, 但按默认导入使用了 ${defaultName}`)
    }
    if (namedBlock) {
      for (const raw of namedBlock.split(',')) {
        const piece = raw.trim().replace(/^type\s+/, '')
        if (!piece) continue
        const name = piece.split(/\s+as\s+/)[0].trim()
        symbolChecks++
        if (name && !targetExports.has(name)) {
          problems.push(`${short}: ${spec} 未导出 ${name}`)
        }
      }
    }
  }

  if (isVue) {
    const templateMatch = text.match(/<template>([\s\S]*)<\/template>/)
    const scriptMatch = text.match(/<script[^>]*setup[^>]*>([\s\S]*?)<\/script>/)
    if (!templateMatch) problems.push(`${short}: 缺少 <template>`)
    if (!scriptMatch) problems.push(`${short}: 缺少 <script setup>`)

    if (templateMatch && scriptMatch) {
      const tpl = templateMatch[1]
      const declared = importedLocalNames(scriptMatch[1])

      const tags = new Set()
      // 只取真正作为组件使用的标签: 排除 <template> 与自闭合插槽 <template #xxx>
      for (const t of tpl.matchAll(/<([A-Z][A-Za-z0-9]*)(?=[\s/>])/g)) tags.add(t[1])

      for (const tag of tags) {
        if (tag.startsWith('El')) continue // Element Plus 全量引入, 无需显式 import
        if (VUE_BUILTINS.has(tag)) continue
        if (globallyRegistered.has(tag)) continue // main.ts 里 app.component() 注册过
        if (!declared.has(tag)) {
          problems.push(`${short}: 模板用了 <${tag}> 但脚本里没有导入/定义, 也不在全局注册列表`)
        }
      }
    }
  }

  // 4: 禁用项
  if (/127\.0\.0\.1:8001|localhost:8001/.test(text)) {
    problems.push(`${short}: 出现硬编码后端地址`)
  }
  if (/:\s*any\b|\bas any\b/.test(text)) problems.push(`${short}: 使用了 any`)
  if (/@ts-ignore|@ts-expect-error/.test(text)) {
    problems.push(`${short}: 使用了 @ts-ignore / @ts-expect-error`)
  }
  if (/api\/hello/.test(text)) problems.push(`${short}: 残留 /api/hello 调用`)
}

console.log(`扫描文件: ${files.length}`)
console.log(`import 语句: ${importCount}, 跨文件符号核对: ${symbolChecks}`)
console.log(`全局注册图标: ${[...globallyRegistered].join(', ') || '(无)'}`)

if (problems.length) {
  console.log(`\n发现 ${problems.length} 个问题:`)
  for (const p of problems) console.log('  - ' + p)
  process.exit(1)
}
console.log('\n前端静态自查通过: 导入路径、导出符号、模板组件来源、禁用项均无问题 ✅')
