/**
 * v-permission 指令: 当前用户缺少权限时把元素从 DOM 中移除。
 *
 * 用法:
 *   <el-button v-permission="'users:write'">新建</el-button>
 *   <el-button v-permission="['users:write', 'users:create']">批量</el-button>
 *   <el-button v-permission:role="'super_admin'">危险操作</el-button>
 */

import type { App, Directive, DirectiveBinding } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { hasPermission, hasRole } from '@/utils/permission'

type PermissionValue = string | string[] | undefined | null

/** 判断当前用户是否满足绑定值 */
function allowed(binding: DirectiveBinding<PermissionValue>): boolean {
  const auth = useAuthStore()
  const value = binding.value
  if (!value || (Array.isArray(value) && value.length === 0)) return true

  if (binding.arg === 'role') {
    return hasRole(auth.roles, value, auth.isSuperuser)
  }
  return hasPermission(auth.permissions, value, auth.isSuperuser)
}

/** 移除元素 (保留注释占位, 便于调试) */
function removeElement(el: HTMLElement): void {
  el.parentNode?.removeChild(el)
}

export const permissionDirective: Directive<HTMLElement, PermissionValue> = {
  mounted(el, binding) {
    if (!allowed(binding)) removeElement(el)
  },
  updated(el, binding) {
    // 权限变化后（例如重新登录）重新判定: 不满足则移除
    if (!allowed(binding)) removeElement(el)
  },
}

/** 注册全局指令 */
export function setupDirectives(app: App): void {
  app.directive('permission', permissionDirective)
}

export default permissionDirective
