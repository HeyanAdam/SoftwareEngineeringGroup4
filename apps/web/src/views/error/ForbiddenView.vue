<script setup lang="ts">
/** 403 页面: 已登录但权限不足 */

import { useRouter } from 'vue-router'
import { ElButton, ElIcon, ElTag } from 'element-plus'
import { HomeFilled, Lock } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function goHome(): void {
  void router.replace('/')
}
</script>

<template>
  <div class="forbidden-view">
    <div class="forbidden-view__badge">
      <ElIcon :size="42"><Lock /></ElIcon>
    </div>
    <div class="forbidden-view__code">403</div>
    <h1 class="forbidden-view__title">无访问权限</h1>
    <p class="forbidden-view__desc">
      当前账号没有访问该页面的权限, 请联系管理员分配相应角色。
    </p>

    <div v-if="authStore.roles.length" class="forbidden-view__roles">
      <span class="text-secondary">当前角色:</span>
      <ElTag v-for="role in authStore.roles" :key="role" size="small" type="info" effect="light">
        {{ role }}
      </ElTag>
    </div>

    <div class="forbidden-view__actions">
      <ElButton type="primary" :icon="HomeFilled" @click="goHome">返回首页</ElButton>
      <ElButton @click="router.replace('/profile')">查看个人资料</ElButton>
    </div>
  </div>
</template>

<style scoped lang="scss">
.forbidden-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 60vh;
  padding: 40px 16px;
  text-align: center;

  &__badge {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 78px;
    height: 78px;
    color: var(--app-color-warning);
    background-color: rgb(217 119 6 / 12%);
    border-radius: 50%;
  }

  &__code {
    font-size: 40px;
    font-weight: 800;
    color: var(--app-text-placeholder);
  }

  &__title {
    font-size: 22px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__desc {
    max-width: 420px;
    font-size: 14px;
    color: var(--app-text-secondary);
  }

  &__roles {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 13px;
  }

  &__actions {
    display: flex;
    gap: 12px;
    margin-top: 10px;
  }
}
</style>
