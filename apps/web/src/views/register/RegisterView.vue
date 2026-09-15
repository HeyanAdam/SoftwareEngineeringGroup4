<script setup lang="ts">
/** 注册页: 创建账号 (username/email/password/full_name) */

import { reactive, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Lock, Message, User, UserFilled } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import type { NormalizedApiError } from '@/types/common'

const authStore = useAuthStore()
const appStore = useAppStore()
const router = useRouter()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  email: '',
  full_name: '',
  password: '',
  confirmPassword: '',
})

/** 密码强度校验: 至少 8 位且同时包含字母与数字 (与后端一致) */
function validatePassword(_rule: unknown, value: string, callback: (error?: Error) => void): void {
  if (!value) return callback(new Error('请输入密码'))
  if (value.length < 8) return callback(new Error('密码至少 8 位'))
  if (value.length > 128) return callback(new Error('密码不能超过 128 位'))
  const hasLetter = /[A-Za-z]/.test(value)
  const hasDigit = /\d/.test(value)
  if (!hasLetter || !hasDigit) return callback(new Error('密码需同时包含字母和数字'))
  return callback()
}

function validateConfirm(_rule: unknown, value: string, callback: (error?: Error) => void): void {
  if (!value) return callback(new Error('请再次输入密码'))
  if (value !== form.password) return callback(new Error('两次输入的密码不一致'))
  return callback()
}

const rules: FormRules<typeof form> = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    {
      pattern: /^[A-Za-z0-9_.-]{3,32}$/,
      message: '3-32 位, 仅支持字母、数字、下划线、点和短横线',
      trigger: 'blur',
    },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  full_name: [{ max: 64, message: '姓名不能超过 64 个字符', trigger: 'blur' }],
  password: [{ required: true, validator: validatePassword, trigger: 'blur' }],
  confirmPassword: [{ required: true, validator: validateConfirm, trigger: 'blur' }],
}

async function handleSubmit(): Promise<void> {
  const instance = formRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  errorMessage.value = ''
  try {
    await authStore.register({
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      full_name: form.full_name.trim() || undefined,
    })
    ElMessage.success('注册成功, 请使用新账号登录')
    await router.replace({ path: '/login', query: { redirect: '/' } })
  } catch (error) {
    const normalized = error as NormalizedApiError
    errorMessage.value = normalized?.message || '注册失败, 请稍后重试'
  } finally {
    submitting.value = false
  }
}

appStore.setTheme('light')
</script>

<template>
  <div class="register-view">
    <section class="register-view__card">
      <header class="register-view__header">
        <h1>创建账号</h1>
        <p class="text-secondary">注册后由管理员分配角色与权限</p>
      </header>

      <ElAlert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="false"
        class="mb-16"
      />

      <ElForm
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="handleSubmit"
      >
        <ElFormItem label="用户名" prop="username">
          <ElInput v-model="form.username" placeholder="3-32 位字母/数字" :prefix-icon="User" />
        </ElFormItem>

        <ElFormItem label="邮箱" prop="email">
          <ElInput v-model="form.email" placeholder="you@example.com" :prefix-icon="Message" />
        </ElFormItem>

        <ElFormItem label="姓名 (可选)" prop="full_name">
          <ElInput v-model="form.full_name" placeholder="真实姓名或昵称" :prefix-icon="UserFilled" />
        </ElFormItem>

        <ElFormItem label="密码" prop="password">
          <ElInput
            v-model="form.password"
            type="password"
            placeholder="至少 8 位, 含字母与数字"
            :prefix-icon="Lock"
            show-password
          />
        </ElFormItem>

        <ElFormItem label="确认密码" prop="confirmPassword">
          <ElInput
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </ElFormItem>

        <ElButton
          type="primary"
          class="full-width"
          size="large"
          :loading="submitting"
          @click="handleSubmit"
        >
          注册
        </ElButton>
      </ElForm>

      <div class="register-view__footer">
        <span class="text-secondary">已有账号?</span>
        <RouterLink to="/login">返回登录</RouterLink>
      </div>
    </section>
  </div>
</template>

<style scoped lang="scss">
.register-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 32px 16px;
  background:
    radial-gradient(900px 500px at 20% 15%, rgb(37 99 235 / 14%), transparent 60%),
    var(--app-bg-page);

  &__card {
    width: 100%;
    max-width: 460px;
    padding: 32px;
    background-color: var(--app-bg-container);
    border-radius: var(--app-radius-lg);
    box-shadow: var(--app-shadow-lg);
  }

  &__header {
    margin-bottom: 20px;

    h1 {
      font-size: 22px;
      font-weight: 600;
      color: var(--app-text-primary);
    }

    p {
      margin-top: 6px;
      font-size: 13px;
    }
  }

  &__footer {
    display: flex;
    gap: 6px;
    justify-content: center;
    margin-top: 18px;
    font-size: 13px;
  }
}
</style>
