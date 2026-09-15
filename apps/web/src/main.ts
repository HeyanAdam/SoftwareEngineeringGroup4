/** 应用入口: Pinia / Router / Element Plus / 全局样式 / 全局指令 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from '@/App.vue'
import router from '@/router'
import { setupDirectives } from '@/directives/permission'
import { useAppStore } from '@/stores/app'

// Element Plus 基础样式与暗色变量
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
// 业务全局样式 (必须放在 Element Plus 之后, 以便覆盖 CSS 变量)
import '@/styles/index.scss'

const app = createApp(App)

// 全局注册 Element Plus 图标 (侧边菜单通过名称动态渲染)
for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component)
}

const pinia = createPinia()
app.use(pinia)

// 主题 / 侧边栏状态需要在挂载前应用到 DOM, 避免闪烁
useAppStore(pinia).init()

app.use(router)
app.use(ElementPlus, { locale: zhCn })
setupDirectives(app)

app.mount('#app')
