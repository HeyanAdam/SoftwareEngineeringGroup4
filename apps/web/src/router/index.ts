/**
 * 路由实例与全局守卫。
 *
 * 守卫流程:
 *  1. 需要登录的页面: 未登录 -> /login?redirect=<当前地址>
 *  2. 已登录但未拉取资料 -> hydrate() 恢复会话
 *  3. meta.permissions / meta.roles 校验 -> 不通过跳 /403
 *  4. 根据 meta.title 与 VITE_APP_TITLE 动态设置文档标题
 *  - 已登录访问 /login 会被重定向到首页
 */

import { createRouter, createWebHistory } from 'vue-router'

import { routes } from '@/router/routes'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { usePermissionStore } from '@/stores/permission'

const DEFAULT_TITLE = import.meta.env.VITE_APP_TITLE ?? 'SG4 管理后台'

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const appStore = useAppStore()
  const authStore = useAuthStore()
  const permissionStore = usePermissionStore()

  appStore.pageLoading = true

  const requiresAuth = to.meta.requiresAuth !== false

  // 1. 未登录访问受保护页面
  if (requiresAuth && !authStore.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  // 2. 已登录: 恢复会话 (只执行一次)
  if (authStore.isAuthenticated && !authStore.hydrated) {
    await authStore.hydrate()
  }

  // 3. 已登录访问登录页 -> 首页
  if (to.path === '/login' && authStore.isAuthenticated) {
    return { path: '/' }
  }

  // 4. 权限校验
  if (requiresAuth && !permissionStore.hasRouteAccess(to.meta)) {
    return { path: '/403' }
  }

  return true
})

router.afterEach((to) => {
  const appStore = useAppStore()
  appStore.pageLoading = false
  appStore.addVisitedView(to.fullPath)
  document.title = to.meta.title ? `${to.meta.title} · ${DEFAULT_TITLE}` : DEFAULT_TITLE
})

router.onError(() => {
  useAppStore().pageLoading = false
})

export default router
