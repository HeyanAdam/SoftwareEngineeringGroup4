import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

import routes from './routes'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  // 切换路由时回到页面顶部
  scrollBehavior: () => ({ top: 0 }),
})

/** 登录 / 注册页：已登录用户进来时直接回首页 */
const AUTH_PAGES = ['/login', '/register']

/**
 * 全局前置守卫：
 * 1. 目标路由需要登录但没有 token -> 跳登录页，并记录 redirect
 * 2. 已登录用户访问登录 / 注册页 -> 直接回首页
 * 3. 目标路由声明了 meta.perm 且当前用户没有该权限 -> 提示并回首页
 *
 * 这里只用本地状态判断，不发额外请求（避免导航被网络阻塞）；
 * 如果本地还没有权限信息（例如换了浏览器），会补一次 /user/me。
 */
router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth === true)
  const perm = typeof to.meta.perm === 'string' ? to.meta.perm : ''

  if (!requiresAuth) {
    if (authStore.isAuthenticated && AUTH_PAGES.includes(to.path)) {
      return { path: '/' }
    }
    return true
  }

  if (!authStore.isAuthenticated) {
    const redirect = to.fullPath
    return {
      path: '/login',
      query: redirect && redirect !== '/' ? { redirect } : {},
    }
  }

  // 有 token 但本地没用户信息 / 没权限信息 -> 先补齐
  if (!authStore.user || authStore.user.permissions === undefined) {
    try {
      await authStore.fetchProfile()
    } catch {
      // 401 已由响应拦截器清理登录态并跳转，这里停止本次导航
      return false
    }
  }

  if (perm && !authStore.hasPerm(perm)) {
    ElMessage.error('没有权限访问该页面')
    return { path: '/' }
  }

  return true
})

export default router
