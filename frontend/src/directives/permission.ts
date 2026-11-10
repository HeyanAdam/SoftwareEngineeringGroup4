import type { Directive } from 'vue'

import { useAuthStore } from '@/stores/auth'

/**
 * 按钮级权限指令: 当前账号缺少所需权限时, 直接把按钮从页面中移除。
 *
 * 用法:
 *   v-permission="'user:manage'"
 *   v-permission="['role:manage', 'perm:view']"  // 需要同时具备
 *
 * 只用于界面显隐; 服务端仍会逐接口校验, 前端指令不能当作安全边界。
 */
export const permission: Directive<HTMLElement, string | string[]> = {
  mounted(el, binding) {
    const auth = useAuthStore()
    const required = Array.isArray(binding.value) ? binding.value : [binding.value]
    if (!required.every((key) => auth.hasPerm(key))) {
      el.remove()
    }
  },
}
