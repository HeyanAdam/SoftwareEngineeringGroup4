<script setup lang="ts">
/** 后台主布局: 侧边栏 + 顶栏 + 页签 + 内容区 */

import { computed, onBeforeUnmount, onMounted } from 'vue'
import { ElBacktop } from 'element-plus'

import AppHeader from '@/components/layout/AppHeader.vue'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import AppTabs from '@/components/layout/AppTabs.vue'
import { useAppStore } from '@/stores/app'
import { useWsStore } from '@/stores/ws'

const appStore = useAppStore()
const wsStore = useWsStore()

const collapsed = computed(() => appStore.sidebarCollapsed)

onMounted(() => {
  // 进入后台即建立 WebSocket 连接 (通知 / 在线状态)
  wsStore.connect()
})

onBeforeUnmount(() => {
  wsStore.disconnect()
})
</script>

<template>
  <div class="default-layout">
    <AppSidebar />

    <div class="default-layout__main" :class="{ 'is-collapsed': collapsed }">
      <AppHeader />
      <AppTabs />
      <main class="default-layout__content">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>

    <ElBacktop :right="28" :bottom="40" />
  </div>
</template>

<style scoped lang="scss">
.default-layout {
  display: flex;
  width: 100%;
  min-height: 100vh;
  background-color: var(--app-bg-page);

  &__main {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    height: 100vh;
    overflow: hidden;
  }

  &__content {
    flex: 1;
    min-height: 0;
    padding: 16px;
    overflow-y: auto;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.16s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
