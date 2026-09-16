<template>
  <el-container class="layout">
    <!-- 左侧导航 -->
    <el-aside width="220px" class="layout-aside">
      <div class="logo">
        <el-icon :size="22"><Notebook /></el-icon>
        <span class="logo-text">考研 AI 导学</span>
      </div>
      <el-menu router :default-active="route.path" class="layout-menu">
        <el-menu-item index="/">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>AI 问答</span>
        </el-menu-item>
        <el-menu-item index="/plans">
          <el-icon><Calendar /></el-icon>
          <span>学习计划</span>
        </el-menu-item>
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container class="layout-body">
      <!-- 顶部栏：面包屑 + 用户下拉 -->
      <el-header class="layout-header">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item v-for="item in breadcrumb" :key="item.title" :to="item.to">
            {{ item.title }}
          </el-breadcrumb-item>
        </el-breadcrumb>

        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-trigger">
            <el-avatar :size="30" class="user-avatar">{{ avatarText }}</el-avatar>
            <span class="user-name">{{ authStore.displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon>
                个人中心
              </el-dropdown-item>
              <el-dropdown-item command="logout" divided>
                <el-icon><SwitchButton /></el-icon>
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <!-- 页面内容 -->
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

/** 下拉菜单命令类型 */
type DropdownCommand = 'profile' | 'logout'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

/** 面包屑：首页固定第一项，当前页面作为第二项（首页时只有一项） */
const breadcrumb = computed(() => {
  const currentTitle = typeof route.meta.title === 'string' ? route.meta.title : ''
  const items: { title: string; to?: string }[] = [{ title: '首页', to: '/' }]
  if (route.path !== '/') {
    items.push({ title: currentTitle || '当前页面' })
  }
  return items
})

/** 头像文字：取昵称首字 */
const avatarText = computed(() => authStore.displayName.charAt(0))

function handleCommand(command: DropdownCommand): void {
  if (command === 'profile') {
    void router.push('/profile')
    return
  }
  authStore.reset()
  ElMessage.success('已退出登录')
  void router.push('/login')
}

onMounted(() => {
  // 刷新页面后补齐用户信息（后端不可用时静默失败，不阻塞页面）
  void authStore.restore()
})
</script>

<style scoped lang="scss">
.layout {
  height: 100vh;
}

.layout-aside {
  background-color: #1f2d3d;
  overflow-x: hidden;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 60px;
  padding: 0 20px;
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.layout-menu {
  border-right: none;
  background-color: transparent;

  // 深色侧边栏配色（Element Plus 菜单默认是浅色的）
  :deep(.el-menu-item) {
    color: #c0c4cc;

    &:hover {
      color: #fff;
      background-color: #2b3a4d;
    }

    &.is-active {
      color: #fff;
      background-color: #409eff;
    }
  }
}

.layout-body {
  min-width: 0;
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  outline: none;
  color: #303133;
}

.user-avatar {
  background-color: #409eff;
  color: #fff;
}

.user-name {
  font-size: 14px;
}

.layout-main {
  background-color: #f5f7fa;
  padding: 20px;
}
</style>
