<script setup lang="ts">
/** 404 页面 */

import { useRouter } from 'vue-router'
import { ElButton } from 'element-plus'
import { Back, HomeFilled } from '@element-plus/icons-vue'

const router = useRouter()

function goHome(): void {
  void router.replace('/')
}

function goBack(): void {
  router.back()
}
</script>

<template>
  <div class="error-view">
    <div class="error-view__code">404</div>
    <h1 class="error-view__title">页面不存在</h1>
    <p class="error-view__desc">您访问的页面已被移除、重命名, 或从未存在过。</p>
    <div class="error-view__actions">
      <ElButton type="primary" :icon="HomeFilled" @click="goHome">返回首页</ElButton>
      <ElButton :icon="Back" @click="goBack">返回上一页</ElButton>
    </div>
  </div>
</template>

<style scoped lang="scss">
.error-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 60vh;
  padding: 40px 16px;
  text-align: center;

  &__code {
    font-size: 84px;
    font-weight: 800;
    line-height: 1;
    color: transparent;
    background: linear-gradient(135deg, #2563eb, #0ea5e9);
    background-clip: text;
  }

  &__title {
    font-size: 22px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__desc {
    font-size: 14px;
    color: var(--app-text-secondary);
  }

  &__actions {
    display: flex;
    gap: 12px;
    margin-top: 10px;
  }
}
</style>
