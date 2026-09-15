/**
 * 路由权限辅助: 生成可访问路由 / 判断路由是否可访问 / 生成菜单树。
 */

import { defineStore } from 'pinia'
import { computed } from 'vue'
import type { RouteRecordRaw } from 'vue-router'

import { routes } from '@/router/routes'
import { useAuthStore } from '@/stores/auth'
import { checkAccess } from '@/utils/permission'

/** 叶子菜单项 (供侧边栏渲染) */
export interface MenuItem {
  path: string
  title: string
  icon?: string
}

/** 判定单个路由的 meta 是否满足当前用户权限 */
function isRouteAllowed(
  route: RouteRecordRaw,
  permissions: readonly string[],
  roles: readonly string[],
  isSuperuser: boolean,
): boolean {
  const meta = route.meta
  if (!meta) return true
  return checkAccess(
    { permissions: [...permissions], roles: [...roles], isSuperuser },
    { permissions: meta.permissions, roles: meta.roles },
  )
}

/**
 * 递归过滤路由表, 只保留当前用户可访问的节点。
 * 父节点若无可见子节点则整枝丢弃。
 */
export function filterRoutesByPermission(
  source: readonly RouteRecordRaw[],
  permissions: readonly string[],
  roles: readonly string[],
  isSuperuser = false,
): RouteRecordRaw[] {
  const result: RouteRecordRaw[] = []

  for (const route of source) {
    if (!isRouteAllowed(route, permissions, roles, isSuperuser)) continue
    const cloned: RouteRecordRaw = { ...route }
    if (route.children && route.children.length > 0) {
      cloned.children = filterRoutesByPermission(route.children, permissions, roles, isSuperuser)
      // 父级没有可见子路由时整枝丢弃
      if (cloned.children.length === 0) continue
    }
    result.push(cloned)
  }

  return result
}

export const usePermissionStore = defineStore('permission', () => {
  const auth = useAuthStore()

  /** 当前用户可访问的完整路由表 */
  const accessibleRoutes = computed<RouteRecordRaw[]>(() =>
    filterRoutesByPermission(routes, auth.permissions, auth.roles, auth.isSuperuser),
  )

  /** 侧边栏菜单 (过滤 hidden 与无标题项) */
  const menuItems = computed<MenuItem[]>(() => {
    const items: MenuItem[] = []
    for (const route of accessibleRoutes.value) {
      if (route.meta?.hidden) continue
      if (!route.meta?.title) continue
      // 只有一个子路由时直接指向子路由, 避免无意义的折叠
      const children = (route.children ?? []).filter(
        (child) => !child.meta?.hidden && child.meta?.title,
      )
      if (children.length === 1 && children[0]) {
        const only = children[0]
        items.push({
          path: only.path.startsWith('/') ? only.path : `${route.path}/${only.path}`.replace(/\/+/g, '/'),
          title: only.meta?.title ?? route.meta.title,
          icon: only.meta?.icon ?? route.meta.icon,
        })
        continue
      }
      items.push({
        path: route.path,
        title: route.meta.title,
        icon: route.meta.icon,
      })
    }
    return items
  })

  /** 判断某个具体路由 (含 meta 声明) 是否可访问 */
  function hasRouteAccess(
    meta: { permissions?: string[]; roles?: string[]; requiresAuth?: boolean } | undefined,
  ): boolean {
    if (!meta) return true
    if (!auth.isAuthenticated) return false
    return checkAccess(
      { permissions: auth.permissions, roles: auth.roles, isSuperuser: auth.isSuperuser },
      { permissions: meta.permissions, roles: meta.roles },
    )
  }

  return { accessibleRoutes, menuItems, hasRouteAccess }
})
