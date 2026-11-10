<template>
  <div class="home-page">
    <el-card shadow="never" class="welcome-card">
      <h2 class="welcome-title">欢迎回来，{{ authStore.displayName }}</h2>
      <p class="welcome-sub">这里是考研 AI 导学平台，从左侧菜单进入需要的功能模块。</p>
    </el-card>

    <el-row :gutter="16" class="entry-row">
      <el-col v-if="authStore.hasPerm('question:practice')" :span="8">
        <el-card shadow="hover" class="entry-card" @click="go('/chat')">
          <h3>AI 问答</h3>
          <p>向 AI 提问刷题、择校、复习规划相关问题</p>
        </el-card>
      </el-col>
      <el-col v-if="authStore.hasPerm('studyplan:view')" :span="8">
        <el-card shadow="hover" class="entry-card" @click="go('/plans')">
          <h3>学习计划</h3>
          <p>查看和维护你的备考计划</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="entry-card" @click="go('/profile')">
          <h3>个人中心</h3>
          <p>维护资料、修改密码</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function go(path: string): void {
  void router.push(path)
}
</script>

<style scoped lang="scss">
.home-page {
  padding: 4px;
}

.welcome-card {
  margin-bottom: 16px;
}

.welcome-title {
  margin: 0 0 8px;
  font-size: 20px;
}

.welcome-sub {
  margin: 0;
  color: #909399;
}

.entry-card {
  cursor: pointer;

  h3 {
    margin: 0 0 6px;
    font-size: 16px;
  }

  p {
    margin: 0;
    color: #909399;
    font-size: 13px;
  }
}
</style>
