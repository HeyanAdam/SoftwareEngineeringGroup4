/**
 * 权限判定工具 (纯函数, 不依赖 Pinia, 便于单测)。
 * 约定:
 *  - 超级管理员 (*:* 或 isSuperuser) 视为拥有全部权限
 *  - 权限码支持 `module:*` 通配 (例如持有 users:* 可覆盖 users:read)
 */

/** 超级管理员的隐式权限标记 */
export const SUPER_PERMISSION = '*:*'

/** 权限集合的判定上下文 */
export interface PermissionContext {
  permissions: string[]
  roles: string[]
  isSuperuser?: boolean
}

/** 归一化入参为字符串数组 (单值 / 数组 / 空值) */
function toCodeList(required: string | readonly string[] | null | undefined): string[] {
  if (required === null || required === undefined) return []
  return typeof required === 'string' ? [required] : [...required]
}

/** 持有权限码 = 精确匹配, 或持有同模块通配 `module:*`, 或持有 `*:*` */
export function hasPermission(
  permissions: readonly string[],
  required: string | readonly string[] | null | undefined,
  isSuperuser = false,
): boolean {
  if (!required) return true
  if (isSuperuser || permissions.includes(SUPER_PERMISSION)) return true

  const needed = toCodeList(required)
  if (needed.length === 0) return true

  // 收集持有的通配模块
  const wildcardModules = new Set<string>()
  for (const code of permissions) {
    const [module, action] = code.split(':')
    if (action === '*' && module) wildcardModules.add(module)
  }

  return needed.every((code) => {
    if (permissions.includes(code)) return true
    const [module] = code.split(':')
    return Boolean(module && wildcardModules.has(module))
  })
}

/** 满足任意一个权限即可 */
export function hasAnyPermission(
  permissions: readonly string[],
  required: readonly string[] | null | undefined,
  isSuperuser = false,
): boolean {
  if (!required || required.length === 0) return true
  if (isSuperuser || permissions.includes(SUPER_PERMISSION)) return true
  return required.some((code) => hasPermission(permissions, code, isSuperuser))
}

/** 角色判定: 满足任意一个角色即可 (role 为空视为不限制) */
export function hasRole(
  roles: readonly string[],
  required: string | readonly string[] | null | undefined,
  isSuperuser = false,
): boolean {
  if (!required) return true
  if (isSuperuser) return true
  const needed = toCodeList(required)
  if (needed.length === 0) return true
  return needed.some((code) => roles.includes(code))
}

/**
 * 综合判定: permissions 与 roles 同时满足 (空数组/未定义视为不限制)。
 * 路由守卫与 v-permission 指令共用此逻辑。
 */
export function checkAccess(
  context: PermissionContext,
  required: { permissions?: readonly string[]; roles?: readonly string[] } | null | undefined,
): boolean {
  if (!required) return true
  return (
    hasPermission(context.permissions, required.permissions, context.isSuperuser) &&
    hasRole(context.roles, required.roles, context.isSuperuser)
  )
}

/** 权限码 -> 中文模块名 (角色页权限树分组标题) */
export const MODULE_LABELS: Record<string, string> = {
  users: '用户管理',
  roles: '角色权限',
  files: '文件管理',
  dashboard: '数据仪表盘',
  chat: '聊天通知',
  system: '系统监控',
}

/** 取模块中文名, 未登记时回退为模块名本身 */
export function moduleLabel(module: string): string {
  return MODULE_LABELS[module] ?? module
}
