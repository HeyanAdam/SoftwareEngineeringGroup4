<script setup lang="ts">
/** 根组件: 仅承载全局配置与路由出口 */
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import { useAppStore } from '@/stores/app'

const appStore = useAppStore()
</script>

<template>
  <ElConfigProvider :locale="zhCn" :z-index="3000">
    <div class="app-root" :class="{ 'is-dark': appStore.isDark }">
      <RouterView v-slot="{ Component }">
        <Transition name="fade-slide" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </div>
  </ElConfigProvider>
</template>

<style scoped lang="scss">
.app-root {
  min-height: 100vh;
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
