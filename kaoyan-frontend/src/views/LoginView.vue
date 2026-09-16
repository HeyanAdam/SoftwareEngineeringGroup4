<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <div class="auth-header">
        <el-icon :size="30" color="#409eff"><Notebook /></el-icon>
        <h2 class="auth-title">考研 AI 导学平台</h2>
        <p class="auth-subtitle">登录后开启你的备考计划</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @submit.prevent
      >
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleLogin">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        <span>没有账号？</span>
        <router-link to="/register">去注册</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'
import type { LoginForm } from '@/types/user'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive<LoginForm>({
  username: '',
  password: '',
})

const rules: FormRules<LoginForm> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
}

/** 登录成功后的跳转地址：优先用 query.redirect，否则回首页 */
function resolveRedirect(): string {
  const raw = route.query.redirect
  const target = Array.isArray(raw) ? raw[0] : raw
  if (typeof target === 'string' && target.startsWith('/')) {
    return target
  }
  return '/'
}

async function handleLogin(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')
    await router.replace(resolveRedirect())
  } catch {
    // 错误提示已由 axios 响应拦截器统一处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.auth-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #e8f0fe 0%, #f5f7fa 55%, #e6f7ff 100%);
}

.auth-card {
  width: 400px;
  border-radius: 12px;
}

.auth-header {
  text-align: center;
  margin-bottom: 12px;
}

.auth-title {
  margin: 8px 0 4px;
  font-size: 20px;
  font-weight: 600;
}

.auth-subtitle {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.submit-btn {
  width: 100%;
}

.auth-footer {
  text-align: center;
  font-size: 13px;
  color: #606266;

  a {
    margin-left: 4px;
    color: #409eff;
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
