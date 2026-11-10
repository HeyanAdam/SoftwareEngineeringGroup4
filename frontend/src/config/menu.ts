/**
 * 左侧菜单配置（唯一数据源）。
 *
 * 每个菜单项声明自己需要的 perm_key，与《权限表》里的 sys_permission.perm_key 一致：
 *    /               首页        无需权限（登录即可）
 *    /chat           AI 问答     question:practice（刷题训练模块）
 *    /plans          学习计划    studyplan:view（督学陪伴模块）
 *    /profile        个人中心    无需权限
 *    /admin/users    用户管理    user:manage（后台管理模块）
 *    /admin/roles    角色权限    role:manage（后台管理模块）
 *    /admin/audit    审计日志    role:manage（审计属于角色管理范畴）
 *
 * 说明：前端按权限过滤只是体验优化，接口层的 403 才是真正的边界。
 */

import {
  Calendar,
  ChatDotRound,
  Document,
  HomeFilled,
  Lock,
  User,
  UserFilled,
} from '@element-plus/icons-vue'
import type { Component } from 'vue'

export interface MenuItem {
  /** 路由路径，与 router/routes.ts 保持一致 */
  path: string
  /** 菜单文案 */
  title: string
  /** Element Plus 图标组件 */
  icon: Component
  /** 需要的权限标识；为空表示登录即可访问 */
  perm?: string
  /** 分组：main 业务菜单 / admin 后台管理 */
  group: 'main' | 'admin'
}

export const MENU_ITEMS: MenuItem[] = [
  { path: '/', title: '首页', icon: HomeFilled, group: 'main' },
  { path: '/chat', title: 'AI 问答', icon: ChatDotRound, perm: 'question:practice', group: 'main' },
  { path: '/plans', title: '学习计划', icon: Calendar, perm: 'studyplan:view', group: 'main' },
  { path: '/profile', title: '个人中心', icon: User, group: 'main' },
  { path: '/admin/users', title: '用户管理', icon: UserFilled, perm: 'user:manage', group: 'admin' },
  { path: '/admin/roles', title: '角色权限', icon: Lock, perm: 'role:manage', group: 'admin' },
  { path: '/admin/audit', title: '审计日志', icon: Document, perm: 'role:manage', group: 'admin' },
]
