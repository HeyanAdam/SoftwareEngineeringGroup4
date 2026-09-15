<script setup lang="ts">
/** 登录页: 用户名/邮箱 + 密码, 支持"记住我"与 redirect 回跳 */

import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElAlert,
  ElButton,
  ElCheckbox,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
  ElMessage,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Key, Lock, User } from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import { getRememberedUsername } from '@/utils/storage'
import type { NormalizedApiError } from '@/types/common'

const authStore = useAuthStore()
const appStore = useAppStore()
const router = useRouter()
const route = useRoute()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const errorMessage = ref('')

const form = reactive({
  username: '',
  password: '',
  remember: false,
})

const appTitle = import.meta.env.VITE_APP_TITLE ?? 'SG4 管理后台'

/** 演示账号 (后端 SEED_DEMO_DATA=1 时创建) */
const DEMO = { username: 'admin', password: 'Admin@123456' }

const rules: FormRules<typeof form> = {
  username: [
    { required: true, message: '请输入用户名或邮箱', trigger: 'blur' },
    { min: 3, max: 64, message: '长度需在 3 到 64 个字符之间', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, max: 128, message: '密码长度不合法', trigger: 'blur' },
  ],
}

const redirectTarget = computed(() => {
  const raw = route.query.redirect
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.startsWith('/') ? value : '/'
})

/** 回填演示账号 */
function fillDemo(): void {
  form.username = DEMO.username
  form.password = DEMO.password
}

async function handleSubmit(): Promise<void> {
  const instance = formRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  errorMessage.value = ''
  try {
    const profile = await authStore.login(
      { username: form.username.trim(), password: form.password },
      form.remember,
    )
    ElMessage.success(`欢迎回来, ${profile.full_name || profile.username}`)
    await router.replace(redirectTarget.value)
  } catch (error) {
    const normalized = error as NormalizedApiError
    errorMessage.value = normalized?.message || '登录失败, 请稍后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  const remembered = getRememberedUsername()
  if (remembered) {
    form.username = remembered
    form.remember = true
  }
  // 登录页固定亮色, 避免暗色下表单对比度不足
  appStore.setTheme('light')
})
</script>

<template>
  <div class="login-view">
    <div class="login-view__panel">
      <aside class="login-view__aside">
        <div class="login-view__brand">
          <div class="login-view__logo">SG</div>
          <h1>{{ appTitle }}</h1>
        </div>
        <p class="login-view__slogan">GitHub 协作管理控制台</p>
        <ul class="login-view__features">
          <li>统一用户与角色权限管理</li>
          <li>仪表盘可视化与实时统计</li>
          <li>MinIO 文件上传与直传下载</li>
          <li>WebSocket 实时聊天与通知</li>
        </ul>
      </aside>

      <section class="login-view__form">
        <h2 class="login-view__form-title">账号登录</h2>
        <p class="login-view__form-desc">请输入账号信息以进入控制台</p>

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
          <ElFormItem label="用户名 / 邮箱" prop="username">
            <ElInput
              v-model="form.username"
              placeholder="请输入用户名或邮箱"
              :prefix-icon="User"
              clearable
              autocomplete="username"
            />
          </ElFormItem>

          <ElFormItem label="密码" prop="password">
            <ElInput
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              autocomplete="current-password"
            />
          </ElFormItem>

          <div class="login-view__options">
            <ElCheckbox v-model="form.remember">记住我</ElCheckbox>
            <ElButton link type="primary" @click="fillDemo">
              <ElIcon><Key /></ElIcon>
              使用演示账号
            </ElButton>
          </div>

          <ElButton
            type="primary"
            class="full-width"
            size="large"
            :loading="submitting"
            @click="handleSubmit"
          >
            登录
          </ElButton>
        </ElForm>

        <div class="login-view__footer">
          <span class="text-secondary">还没有账号?</span>
          <RouterLink to="/register">立即注册</RouterLink>
        </div>

        <ElAlert
          type="info"
          :closable="false"
          show-icon
          title="演示账号: admin / Admin@123456"
          description="首次部署时由后端自动写入, 生产环境请及时修改密码。"
        />
      </section>
    </div>
  </div>
</template>

<style scoped lang="scss">
.login-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(1200px 600px at 15% 20%, rgb(37 99 235 / 18%), transparent 60%),
    radial-gradient(900px 500px at 85% 80%, rgb(14 165 233 / 16%), transparent 55%),
    var(--app-bg-page);

  &__panel {
    display: grid;
    grid-template-columns: 1.05fr 1fr;
    width: 100%;
    max-width: 940px;
    overflow: hidden;
    background-color: var(--app-bg-container);
    border-radius: var(--app-radius-lg);
    box-shadow: var(--app-shadow-lg);
  }

  &__aside {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 18px;
    padding: 44px 40px;
    color: #e2e8f0;
    background: linear-gradient(160deg, #1e3a8a 0%, #111827 100%);
  }

  &__brand {
    display: flex;
    gap: 14px;
    align-items: center;

    h1 {
      font-size: 20px;
      font-weight: 600;
      color: #f8fafc;
    }
  }

  &__logo {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    font-weight: 700;
    color: #fff;
    background: linear-gradient(135deg, #2563eb, #0ea5e9);
    border-radius: 12px;
  }

  &__slogan {
    font-size: 14px;
    color: #94a3b8;
  }

  &__features {
    display: flex;
    flex-direction: column;
    gap: 10px;
    font-size: 13px;
    color: #cbd5e1;

    li {
      padding-left: 16px;
      position: relative;

      &::before {
        position: absolute;
        left: 0;
        color: #38bdf8;
        content: '▸';
      }
    }
  }

  &__form {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 44px 40px;
  }

  &__form-title {
    font-size: 22px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__form-desc {
    margin: 6px 0 22px;
    font-size: 13px;
    color: var(--app-text-secondary);
  }

  &__options {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 18px;
  }

  &__footer {
    display: flex;
    gap: 6px;
    justify-content: center;
    margin: 18px 0 16px;
    font-size: 13px;
  }
}

@media (width <= 900px) {
  .login-view__panel {
    grid-template-columns: 1fr;
  }

  .login-view__aside {
    display: none;
  }
}
</style>
