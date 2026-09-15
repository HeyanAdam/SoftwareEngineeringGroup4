/** 路由 meta 类型增强: 统一菜单 / 权限声明 */

import 'vue-router'

declare module 'vue-router' {
  interface RouteMeta {
    /** 菜单与浏览器标题 */
    title?: string
    /** Element Plus 图标组件名 (见 @element-plus/icons-vue) */
    icon?: string
    /** 是否需要登录, 默认 true */
    requiresAuth?: boolean
    /** 需要的权限码 (全部满足) */
    permissions?: string[]
    /** 需要的角色 (满足其一) */
    roles?: string[]
    /** 是否从侧边菜单隐藏 */
    hidden?: boolean
  }
}
