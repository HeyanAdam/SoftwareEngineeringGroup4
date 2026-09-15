<script setup lang="ts">
/** 页签栏 (可选): 展示已访问路由, 支持关闭与刷新 */

import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElScrollbar, ElTag } from 'element-plus'

import { useAppStore } from '@/stores/app'
import { HOME_PATH } from '@/router/routes'

const appStore = useAppStore()
const router = useRouter()
const route = useRoute()

/** 当前打开的所有页签 (置顶固定首页) */
const tabs = computed(() => {
  const paths = appStore.visitedViews.filter((path) => path !== HOME_PATH)
  const list = paths.filter((path) => !path.startsWith('/403') && !path.startsWith('/404'))
  return [HOME_PATH, ...list]
})

function titleOf(path: string): string {
  if (path === HOME_PATH) return '数据仪表盘'
  const resolved = router.resolve(path)
  return resolved.meta.title ?? path
}

function isActive(path: string): boolean {
  return route.path === path
}

function goTo(path: string): void {
  if (!isActive(path)) void router.push(path)
}

function closeTab(path: string): void {
  if (path === HOME_PATH) return
  const index = tabs.value.indexOf(path)
  appStore.removeVisitedView(path)
  if (isActive(path)) {
    const fallback = tabs.value[index - 1] ?? HOME_PATH
    void router.push(fallback)
  }
}
</script>

<template>
  <div class="app-tabs">
    <ElScrollbar>
      <div class="app-tabs__list">
        <ElTag
          v-for="path in tabs"
          :key="path"
          :closable="path !== HOME_PATH"
          :effect="isActive(path) ? 'dark' : 'plain'"
          :type="isActive(path) ? 'primary' : 'info'"
          size="default"
          class="app-tabs__item"
          @click="goTo(path)"
          @close="closeTab(path)"
        >
          {{ titleOf(path) }}
        </ElTag>
      </div>
    </ElScrollbar>
  </div>
</template>

<style scoped lang="scss">
.app-tabs {
  padding: 8px 16px 0;
  background-color: var(--app-bg-container);

  &__list {
    display: flex;
    gap: 8px;
    padding-bottom: 8px;
    white-space: nowrap;
  }

  &__item {
    cursor: pointer;
    user-select: none;
  }
}
</style>
