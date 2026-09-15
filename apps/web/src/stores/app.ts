/** 应用级 UI 状态: 侧边栏折叠 / 主题 / 全局加载 */

import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'

import { StorageKey, getBoolean, getItem, setBoolean, setItem } from '@/utils/storage'

export type ThemeMode = 'light' | 'dark'

/** 读取持久化主题, 缺省跟随系统偏好 */
function readInitialTheme(): ThemeMode {
  const saved = getItem(StorageKey.theme)
  if (saved === 'light' || saved === 'dark') return saved
  try {
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

/** 把主题写到 <html> 上, Element Plus 通过 .dark 类切换暗色变量 */
function applyThemeToDom(theme: ThemeMode): void {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.dataset.theme = theme
  root.style.colorScheme = theme
}

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const theme = ref<ThemeMode>('light')
  /** 全局页面加载 (路由切换 / 长任务) */
  const pageLoading = ref(false)
  /** 已打开的页签 (AppTabs 使用) */
  const visitedViews = ref<string[]>([])

  const isDark = computed(() => theme.value === 'dark')

  /** 初始化: 恢复持久化设置并应用到 DOM */
  function init(): void {
    theme.value = readInitialTheme()
    sidebarCollapsed.value = getBoolean(StorageKey.sidebarCollapsed)
    applyThemeToDom(theme.value)
  }

  /** 切换侧边栏折叠 */
  function toggleSidebar(value?: boolean): void {
    sidebarCollapsed.value = value ?? !sidebarCollapsed.value
    setBoolean(StorageKey.sidebarCollapsed, sidebarCollapsed.value)
  }

  /** 设置主题 */
  function setTheme(value: ThemeMode): void {
    theme.value = value
  }

  /** 在亮/暗之间切换 */
  function toggleTheme(): void {
    setTheme(isDark.value ? 'light' : 'dark')
  }

  /** 记录访问过的路由 (供页签栏使用) */
  function addVisitedView(path: string): void {
    if (!visitedViews.value.includes(path)) visitedViews.value.push(path)
  }

  /** 移除页签 */
  function removeVisitedView(path: string): void {
    visitedViews.value = visitedViews.value.filter((item) => item !== path)
  }

  // 主题持久化 + 同步 DOM
  watch(theme, (value) => {
    applyThemeToDom(value)
    setItem(StorageKey.theme, value)
  })

  return {
    sidebarCollapsed,
    theme,
    isDark,
    pageLoading,
    visitedViews,
    init,
    toggleSidebar,
    setTheme,
    toggleTheme,
    addVisitedView,
    removeVisitedView,
  }
})
