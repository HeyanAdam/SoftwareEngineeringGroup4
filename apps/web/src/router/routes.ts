/**
 * 路由表定义。
 * meta 说明:
 *   title       菜单 / 面包屑 / 文档标题
 *   icon        Element Plus 图标组件名
 *   requiresAuth 是否需要登录 (默认 true)
 *   permissions 需要的权限码 (全部满足; 超级管理员直通)
 *   roles       需要的角色 (满足其一)
 *   hidden      是否从侧边菜单隐藏
 */

import type { RouteRecordRaw } from 'vue-router'

export const LOGIN_PATH = '/login'
export const HOME_PATH = '/dashboard'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/LoginView.vue'),
    meta: { title: '登录', requiresAuth: false, hidden: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/register/RegisterView.vue'),
    meta: { title: '注册账号', requiresAuth: false, hidden: true },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/ForbiddenView.vue'),
    meta: { title: '无访问权限', requiresAuth: false, hidden: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/DefaultLayout.vue'),
    redirect: HOME_PATH,
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: { title: '数据仪表盘', icon: 'DataLine', permissions: ['dashboard:read'] },
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/users/UserListView.vue'),
        meta: { title: '用户管理', icon: 'User', permissions: ['users:read'] },
      },
      {
        path: 'roles',
        name: 'Roles',
        component: () => import('@/views/roles/RoleListView.vue'),
        meta: { title: '角色权限', icon: 'Key', permissions: ['roles:read'] },
      },
      {
        path: 'files',
        name: 'Files',
        component: () => import('@/views/files/FileListView.vue'),
        meta: { title: '文件管理', icon: 'FolderOpened', permissions: ['files:read'] },
      },
      {
        path: 'chat',
        name: 'Chat',
        component: () => import('@/views/chat/ChatView.vue'),
        meta: { title: '协作聊天', icon: 'ChatDotRound', permissions: ['chat:read'] },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/ProfileView.vue'),
        meta: { title: '个人中心', icon: 'Setting' },
      },
      {
        path: '404',
        name: 'NotFound',
        component: () => import('@/views/error/NotFoundView.vue'),
        meta: { title: '页面不存在', hidden: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/404',
    meta: { hidden: true },
  },
]
