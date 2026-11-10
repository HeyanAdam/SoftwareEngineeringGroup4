<template>
  <el-container class="layout">
    <!-- 左侧导航：菜单项由权限驱动，没有权限的菜单不会渲染 -->
    <el-aside width="220px" class="layout-aside">
      <div class="logo">
        <el-icon :size="22"><Notebook /></el-icon>
        <span class="logo-text">考研 AI 导学</span>
      </div>
      <el-menu router :default-active="route.path" class="layout-menu">
        <el-menu-item v-for="item in mainMenus" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>

        <template v-if="adminMenus.length > 0">
          <div class="menu-group-title">后台管理</div>
          <el-menu-item v-for="item in adminMenus" :key="item.path" :index="item.path">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </el-menu-item>
        </template>
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

import { MENU_ITEMS } from '@/config/menu'
import { useAuthStore } from '@/stores/auth'

/** 下拉菜单命令类型 */
type DropdownCommand = 'profile' | 'logout'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

/** 业务菜单：按 hasPerm 过滤（无 perm 的项登录即可见） */
const mainMenus = computed(() =>
  MENU_ITEMS.filter((item) => item.group === 'main' && authStore.hasPerm(item.perm)),
)

/** 后台菜单：只有拥有 user:manage / role:manage 的人能看到 */
const adminMenus = computed(() =>
  MENU_ITEMS.filter((item) => item.group === 'admin' && authStore.hasPerm(item.perm)),
)

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

async function handleCommand(command: DropdownCommand): Promise<void> {
  if (command === 'profile') {
    void router.push('/profile')
    return
  }
  // 退出登录会调用后端 /user/logout，把当前令牌加入吊销名单
  await authStore.logout()
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

.menu-group-title {
  padding: 14px 20px 6px;
  color: #8a94a6;
  font-size: 12px;
  letter-spacing: 1px;
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
