<script setup lang="ts">
/** 侧边栏: 菜单来自 permission store 的可访问路由 */

import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElIcon, ElMenu, ElMenuItem, ElScrollbar } from 'element-plus'

import { useAppStore } from '@/stores/app'
import { usePermissionStore } from '@/stores/permission'

const appStore = useAppStore()
const permissionStore = usePermissionStore()
const route = useRoute()

const appTitle = import.meta.env.VITE_APP_TITLE ?? 'SG4 管理后台'
const collapsed = computed(() => appStore.sidebarCollapsed)
const activePath = computed(() => route.path)
const menus = computed(() => permissionStore.menuItems)
</script>

<template>
  <aside class="app-sidebar" :class="{ 'is-collapsed': collapsed }">
    <div class="app-sidebar__brand">
      <div class="app-sidebar__logo">SG</div>
      <Transition name="fade">
        <span v-if="!collapsed" class="app-sidebar__title">{{ appTitle }}</span>
      </Transition>
    </div>

    <ElScrollbar class="app-sidebar__scroll">
      <ElMenu
        :default-active="activePath"
        :collapse="collapsed"
        :collapse-transition="false"
        background-color="transparent"
        text-color="var(--app-sidebar-text)"
        active-text-color="var(--app-sidebar-text-active)"
        router
        unique-opened
      >
        <ElMenuItem v-for="menu in menus" :key="menu.path" :index="menu.path">
          <ElIcon v-if="menu.icon">
            <component :is="menu.icon" />
          </ElIcon>
          <template #title>{{ menu.title }}</template>
        </ElMenuItem>
      </ElMenu>
    </ElScrollbar>

    <div v-if="!collapsed" class="app-sidebar__footer">
      <span class="text-mono">v0.1.0</span>
    </div>
  </aside>
</template>

<style scoped lang="scss">
.app-sidebar {
  display: flex;
  flex-direction: column;
  width: var(--app-sidebar-width);
  height: 100vh;
  background-color: var(--app-sidebar-bg);
  transition: width 0.22s ease;

  &.is-collapsed {
    width: var(--app-sidebar-width-collapsed);
  }

  &__brand {
    display: flex;
    gap: 10px;
    align-items: center;
    height: var(--app-header-height);
    padding: 0 16px;
    overflow: hidden;
    border-bottom: 1px solid rgb(255 255 255 / 6%);
  }

  &__logo {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    background: linear-gradient(135deg, #2563eb, #0ea5e9);
    border-radius: 9px;
  }

  &__title {
    font-size: 15px;
    font-weight: 600;
    color: #f8fafc;
    white-space: nowrap;
  }

  &__scroll {
    flex: 1;
    min-height: 0;
    padding: 10px 8px;
  }

  &__footer {
    padding: 12px 16px;
    font-size: 11px;
    color: var(--app-sidebar-text);
    text-align: center;
    border-top: 1px solid rgb(255 255 255 / 6%);
  }

  :deep(.el-menu) {
    border-right: none;
  }

  :deep(.el-menu-item) {
    height: 42px;
    margin-bottom: 4px;
    border-radius: var(--app-radius-sm);

    &:hover {
      background-color: var(--app-sidebar-bg-hover);
    }

    &.is-active {
      font-weight: 600;
      background-color: var(--app-color-primary);
    }
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
