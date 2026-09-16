import { createRouter, createWebHistory } from 'vue-router'

import routes from './routes'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  // 切换路由时回到页面顶部
  scrollBehavior: () => ({ top: 0 }),
})

/** 需要登录才能访问的页面 */
const AUTH_PAGES = ['/login', '/register']

/**
 * 全局前置守卫：
 * 1. 目标路由需要登录但没有 token -> 跳登录页，并记录 redirect
 * 2. 已登录用户访问登录 / 注册页 -> 直接回首页
 * 这里只用同步的 token 判断，不发请求，避免导航被网络阻塞。
 */
router.beforeEach((to) => {
  const authStore = useAuthStore()
  // to.matched 为空说明命中了 404 通配路由
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth === true)

  if (requiresAuth && !authStore.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (authStore.isAuthenticated && AUTH_PAGES.includes(to.path)) {
    return { path: '/' }
  }

  return true
})

export default router
