<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <div class="auth-header">
        <el-icon :size="30" color="#409eff"><UserFilled /></el-icon>
        <h2 class="auth-title">注册新账号</h2>
        <p class="auth-subtitle">填写基本信息，开始你的考研之旅</p>
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
          <el-input v-model="form.username" placeholder="用于登录，建议 3-20 位" clearable />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="example@mail.com" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="handleRegister">
            注 册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        <span>已有账号？</span>
        <router-link to="/login">去登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormItemRule, FormRules } from 'element-plus'

import { register } from '@/api/auth'
import type { RegisterForm } from '@/types/user'

const router = useRouter()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive<RegisterForm>({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

/** 确认密码校验：与 password 字段比较 */
const validateConfirmPassword: FormItemRule['validator'] = (_rule, value, callback) => {
  if (typeof value !== 'string' || value.length === 0) {
    callback(new Error('请再次输入密码'))
    return
  }
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
    return
  }
  callback()
}

const rules: FormRules<RegisterForm> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 位', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱格式', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
  confirmPassword: [{ required: true, validator: validateConfirmPassword, trigger: 'blur' }],
}

async function handleRegister(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await register({
      username: form.username,
      email: form.email,
      password: form.password,
    })
    ElMessage.success('注册成功，请登录')
    await router.push('/login')
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
  width: 420px;
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
