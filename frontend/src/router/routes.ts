import type { RouteRecordRaw } from 'vue-router'

import DefaultLayout from '@/layouts/DefaultLayout.vue'

/**
 * 路由表：
 * - /login、/register 是无布局的独立页面
 * - 其余业务页面挂在 DefaultLayout（左侧菜单 + 顶部栏）下
 * - meta.requiresAuth 为 true 的路由由全局前置守卫校验 token
 * - meta.perm 声明访问该页需要的权限标识，守卫会与用户权限比对
 *   （服务端仍会逐接口校验，这里只是不让人点进一个必然 403 的页面）
 * - meta.title 同时用于浏览器标题与顶部栏标题
 */
export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/RegisterView.vue'),
    meta: { title: '注册' },
  },
  {
    path: '/',
    component: DefaultLayout,
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('@/views/HomeView.vue'),
        meta: { title: '首页', requiresAuth: true },
      },
      {
        path: 'chat',
        name: 'chat',
        component: () => import('@/views/ChatView.vue'),
        meta: { title: 'AI 问答', requiresAuth: true, perm: 'question:practice' },
      },
      {
        path: 'plans',
        name: 'plans',
        component: () => import('@/views/PlanView.vue'),
        meta: { title: '学习计划', requiresAuth: true, perm: 'studyplan:view' },
      },
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '个人中心', requiresAuth: true },
      },
      {
        path: 'admin/users',
        name: 'admin-users',
        component: () => import('@/views/admin/UserManageView.vue'),
        meta: { title: '用户管理', requiresAuth: true, perm: 'user:manage' },
      },
      {
        path: 'admin/audit',
        name: 'admin-audit',
        component: () => import('@/views/admin/AuditLogView.vue'),
        meta: { title: '审计日志', requiresAuth: true, perm: 'role:manage' },
      },
      {
        path: 'admin/roles',
        name: 'admin-roles',
        component: () => import('@/views/admin/RoleManageView.vue'),
        meta: { title: '角色权限', requiresAuth: true, perm: 'role:manage' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '页面不存在' },
  },
]

export default routes
