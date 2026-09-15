<script setup lang="ts">
/** 顶栏: 折叠按钮 / 面包屑 / 主题切换 / 全屏 / 通知 / 用户菜单 */

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElAvatar,
  ElBadge,
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElEmpty,
  ElIcon,
  ElMessage,
  ElMessageBox,
  ElPopover,
  ElScrollbar,
  ElTag,
  ElTooltip,
} from 'element-plus'
import {
  Bell,
  Expand,
  Fold,
  FullScreen,
  Moon,
  SwitchButton,
  Sunny,
  User,
} from '@element-plus/icons-vue'

import AppBreadcrumb from '@/components/layout/AppBreadcrumb.vue'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { useWsStore } from '@/stores/ws'
import { formatRelativeTime, initialsOf } from '@/utils/format'
import type { NotificationLevel } from '@/types/chat'

const appStore = useAppStore()
const authStore = useAuthStore()
const wsStore = useWsStore()
const router = useRouter()

const isFullscreen = ref(false)
const notificationVisible = ref(false)

const collapsed = computed(() => appStore.sidebarCollapsed)
const isDark = computed(() => appStore.isDark)
const notifications = computed(() => wsStore.notifications)
const unread = computed(() => wsStore.unreadCount)

/** 通知级别 -> Element Plus tag 类型 */
const LEVEL_TAG: Record<NotificationLevel, 'primary' | 'success' | 'warning' | 'danger'> = {
  info: 'primary',
  success: 'success',
  warning: 'warning',
  error: 'danger',
}

const LEVEL_LABEL: Record<NotificationLevel, string> = {
  info: '提示',
  success: '成功',
  warning: '警告',
  error: '错误',
}

/** 连接状态展示 */
const connectionTag = computed(() => {
  const status = wsStore.status
  if (status === 'open') return { type: 'success' as const, text: '实时已连接' }
  if (status === 'connecting' || status === 'reconnecting')
    return { type: 'warning' as const, text: '连接中…' }
  return { type: 'info' as const, text: '实时未连接' }
})

function toggleSidebar(): void {
  appStore.toggleSidebar()
}

function toggleTheme(): void {
  appStore.toggleTheme()
}

function syncFullscreen(): void {
  isFullscreen.value = Boolean(document.fullscreenElement)
}

async function toggleFullscreen(): Promise<void> {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await document.documentElement.requestFullscreen()
    }
  } catch {
    ElMessage.warning('当前浏览器不支持全屏')
  } finally {
    syncFullscreen()
  }
}

function openNotifications(visible: boolean): void {
  notificationVisible.value = visible
  if (visible) wsStore.markNotificationsRead()
}

async function handleUserCommand(command: string): Promise<void> {
  if (command === 'profile') {
    await router.push('/profile')
    return
  }
  if (command === 'logout') {
    try {
      await ElMessageBox.confirm('确定要退出当前账号吗?', '退出登录', {
        type: 'warning',
        confirmButtonText: '退出',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
    await authStore.logout()
    wsStore.disconnect()
    ElMessage.success('已退出登录')
    await router.replace({ path: '/login' })
  }
}

onMounted(() => {
  document.addEventListener('fullscreenchange', syncFullscreen)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', syncFullscreen)
})
</script>

<template>
  <header class="app-header">
    <div class="app-header__left">
      <ElButton text class="app-header__icon-btn" @click="toggleSidebar">
        <ElIcon :size="18">
          <component :is="collapsed ? Expand : Fold" />
        </ElIcon>
      </ElButton>
      <AppBreadcrumb />
    </div>

    <div class="app-header__right">
      <ElTag :type="connectionTag.type" size="small" effect="light" round>
        {{ connectionTag.text }}
      </ElTag>

      <ElTooltip :content="isDark ? '切换到亮色模式' : '切换到暗色模式'" placement="bottom">
        <ElButton text class="app-header__icon-btn" @click="toggleTheme">
          <ElIcon :size="18">
            <component :is="isDark ? Sunny : Moon" />
          </ElIcon>
        </ElButton>
      </ElTooltip>

      <ElTooltip :content="isFullscreen ? '退出全屏' : '全屏显示'" placement="bottom">
        <ElButton text class="app-header__icon-btn" @click="toggleFullscreen">
          <ElIcon :size="18">
            <component :is="isFullscreen ? SwitchButton : FullScreen" />
          </ElIcon>
        </ElButton>
      </ElTooltip>

      <ElPopover
        :visible="notificationVisible"
        placement="bottom-end"
        width="340"
        trigger="click"
        popper-class="app-notification-popper"
        @update:visible="openNotifications"
      >
        <template #reference>
          <ElBadge :value="unread" :hidden="unread === 0" :max="99" class="app-header__badge">
            <ElButton text class="app-header__icon-btn">
              <ElIcon :size="18"><Bell /></ElIcon>
            </ElButton>
          </ElBadge>
        </template>

        <div class="notification-panel">
          <div class="notification-panel__header">
            <span>通知中心</span>
            <ElButton v-if="notifications.length" link type="primary" @click="wsStore.clearNotifications()">
              清空
            </ElButton>
          </div>
          <ElScrollbar max-height="320px">
            <ul v-if="notifications.length" class="notification-panel__list">
              <li v-for="item in notifications" :key="item.id" class="notification-panel__item">
                <div class="notification-panel__title">
                  <ElTag :type="LEVEL_TAG[item.level]" size="small" effect="light">
                    {{ LEVEL_LABEL[item.level] }}
                  </ElTag>
                  <span>{{ item.title }}</span>
                </div>
                <p class="notification-panel__content">{{ item.content }}</p>
                <span class="notification-panel__time">{{ formatRelativeTime(item.receivedAt) }}</span>
              </li>
            </ul>
            <ElEmpty v-else description="暂无通知" :image-size="64" />
          </ElScrollbar>
        </div>
      </ElPopover>

      <ElDropdown trigger="click" @command="handleUserCommand">
        <div class="app-header__user">
          <ElAvatar :size="32" :src="authStore.user?.avatar ?? undefined">
            {{ initialsOf(authStore.displayName) }}
          </ElAvatar>
          <div class="app-header__user-meta">
            <span class="app-header__user-name">{{ authStore.displayName }}</span>
            <span class="app-header__user-role">
              {{ authStore.isSuperuser ? '超级管理员' : (authStore.roles[0] ?? '普通用户') }}
            </span>
          </div>
        </div>
        <template #dropdown>
          <ElDropdownMenu>
            <ElDropdownItem command="profile" :icon="User">个人中心</ElDropdownItem>
            <ElDropdownItem command="logout" :icon="SwitchButton" divided>退出登录</ElDropdownItem>
          </ElDropdownMenu>
        </template>
      </ElDropdown>
    </div>
  </header>
</template>

<style scoped lang="scss">
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--app-header-height);
  padding: 0 16px;
  background-color: var(--app-bg-container);
  border-bottom: 1px solid var(--app-border-color-light);

  &__left,
  &__right {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  &__icon-btn {
    width: 34px;
    height: 34px;
    padding: 0;
    color: var(--app-text-secondary);

    &:hover {
      color: var(--app-color-primary);
      background-color: var(--app-bg-hover);
    }
  }

  &__badge {
    display: flex;
    align-items: center;
  }

  &__user {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 4px 8px;
    cursor: pointer;
    border-radius: var(--app-radius-sm);
    transition: background-color 0.18s ease;

    &:hover {
      background-color: var(--app-bg-hover);
    }
  }

  &__user-meta {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }

  &__user-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__user-role {
    font-size: 11px;
    color: var(--app-text-placeholder);
  }
}

.notification-panel {
  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 8px;
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 600;
    border-bottom: 1px solid var(--app-border-color-light);
  }

  &__list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  &__item {
    padding-bottom: 8px;
    border-bottom: 1px dashed var(--app-border-color-light);

    &:last-child {
      border-bottom: none;
    }
  }

  &__title {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 13px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__content {
    margin-top: 4px;
    font-size: 12px;
    color: var(--app-text-secondary);
  }

  &__time {
    font-size: 11px;
    color: var(--app-text-placeholder);
  }
}
</style>
