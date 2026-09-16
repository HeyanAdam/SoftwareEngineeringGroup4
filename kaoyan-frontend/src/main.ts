import { createApp } from 'vue'
import type { Component } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import {
  ArrowDown,
  Calendar,
  ChatDotRound,
  HomeFilled,
  Lock,
  Notebook,
  Promotion,
  School,
  SwitchButton,
  User,
  UserFilled,
} from '@element-plus/icons-vue'

import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

// 全量引入 Element Plus，并设置中文语言包（日期选择器、确认弹窗等文案）
app.use(ElementPlus, { locale: zhCn })

// 图标按需具名注册（只注册模板里以 <Xxx /> 形式直接使用的图标）
// 注意：tsconfig 开了 noUncheckedIndexedAccess，所以用 entries + 判空而不是下标取值
const icons: Record<string, Component> = {
  ArrowDown,
  Calendar,
  ChatDotRound,
  HomeFilled,
  Lock,
  Notebook,
  Promotion,
  School,
  SwitchButton,
  User,
  UserFilled,
}

for (const [name, icon] of Object.entries(icons)) {
  if (icon) {
    app.component(name, icon)
  }
}

app.mount('#app')
