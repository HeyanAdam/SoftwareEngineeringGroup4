<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <el-icon :size="26" color="#409eff"><Notebook /></el-icon>
        <span class="login-title">考研 AI 导学平台</span>
      </div>

      <el-tabs v-model="activeTab" stretch class="login-tabs">
        <!-- 方式一：用户名 + 密码 -->
        <el-tab-pane label="账号登录" name="password">
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-position="top"
            @keyup.enter="submitPassword"
          >
            <el-form-item label="用户名 / 邮箱" prop="username">
              <el-input v-model="passwordForm.username" placeholder="请输入用户名或已绑定邮箱" clearable />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="passwordForm.password"
                type="password"
                placeholder="请输入密码"
                show-password
                clearable
              />
            </el-form-item>
            <el-form-item v-if="showCaptcha" label="图形验证码">
              <div class="code-row">
                <el-input
                  v-model="passwordForm.captcha_code"
                  placeholder="4 位字符，不区分大小写"
                  maxlength="4"
                  clearable
                />
                <div class="captcha-box" title="看不清？点击刷新" @click="refreshCaptcha" v-html="captchaSvg"></div>
              </div>
            </el-form-item>
            <el-button type="primary" class="submit-button" :loading="loading" @click="submitPassword">
              登录
            </el-button>
          </el-form>
        </el-tab-pane>

        <!-- 方式二：邮箱验证码 -->
        <el-tab-pane label="邮箱验证码" name="email">
          <el-form
            ref="emailFormRef"
            :model="emailForm"
            :rules="emailRules"
            label-position="top"
            @keyup.enter="submitEmail"
          >
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="emailForm.email" placeholder="请输入注册时填写的邮箱" clearable />
            </el-form-item>
            <el-form-item label="验证码" prop="code">
              <div class="code-row">
                <el-input v-model="emailForm.code" placeholder="6 位数字验证码" maxlength="6" clearable />
                <el-button :disabled="countdown > 0" :loading="sending" @click="sendCode('login')">
                  {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
                </el-button>
              </div>
            </el-form-item>
            <el-button type="primary" class="submit-button" :loading="loading" @click="submitEmail">
              登录
            </el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <div class="login-footer">
        <el-link type="primary" :underline="false" @click="resetVisible = true">忘记密码</el-link>
        <el-link type="primary" :underline="false" @click="goRegister">没有账号？去注册</el-link>
      </div>
    </div>

    <!-- 忘记密码：邮箱验证码重置 -->
    <el-dialog v-model="resetVisible" title="重置密码" width="420px">
      <el-form ref="resetFormRef" :model="resetForm" :rules="resetRules" label-position="top">
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="resetForm.email" placeholder="请输入注册邮箱" clearable />
        </el-form-item>
        <el-form-item label="验证码" prop="code">
          <div class="code-row">
            <el-input v-model="resetForm.code" placeholder="6 位数字验证码" maxlength="6" clearable />
            <el-button :disabled="countdown > 0" :loading="sending" @click="sendCode('reset')">
              {{ countdown > 0 ? `${countdown}s` : '获取验证码' }}
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="resetForm.new_password"
            type="password"
            placeholder="至少 8 位，需包含字母和数字"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submitReset">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import { getCaptcha, resetPassword, sendEmailCode } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { EmailLoginForm, LoginForm, LoginPayload, ResetPasswordPayload } from '@/types/user'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

/** 当前登录方式：password / email */
const activeTab = ref<'password' | 'email'>('password')
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)
const resetVisible = ref(false)

const passwordFormRef = ref<FormInstance>()
const emailFormRef = ref<FormInstance>()
const resetFormRef = ref<FormInstance>()

const passwordForm = reactive<LoginForm & { captcha_code: string }>({
  username: '',
  password: '',
  captcha_code: '',
})

/** 图形验证码：密码登录失败后强制展示（服务端在失败满 2 次后返回 40010 强制要求） */
const showCaptcha = ref(false)
const captchaSvg = ref('')
const captchaId = ref('')

async function refreshCaptcha(): Promise<void> {
  try {
    const res = await getCaptcha()
    captchaId.value = res.captcha_id
    captchaSvg.value = res.svg
  } catch {
    // 错误提示已由响应拦截器统一处理
  }
}
const emailForm = reactive<EmailLoginForm>({ email: '', code: '' })
const resetForm = reactive<ResetPasswordPayload>({ email: '', code: '', new_password: '' })

const passwordRules: FormRules = {
  username: [{ required: true, message: '请输入用户名或邮箱', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

const emailRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { pattern: emailPattern, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '验证码为 6 位数字', trigger: 'blur' },
  ],
}

const resetRules: FormRules = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { pattern: emailPattern, message: '邮箱格式不正确', trigger: 'blur' },
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '验证码为 6 位数字', trigger: 'blur' },
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少 8 位', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        const hasLetter = /[A-Za-z]/.test(value)
        const hasDigit = /\d/.test(value)
        if (value && (!hasLetter || !hasDigit)) {
          callback(new Error('密码必须同时包含字母和数字'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

let timer: ReturnType<typeof setInterval> | undefined

/** 发送验证码并开始 60 秒倒计时 */
async function sendCode(purpose: 'login' | 'reset'): Promise<void> {
  const email = purpose === 'login' ? emailForm.email : resetForm.email
  if (!emailPattern.test(email)) {
    ElMessage.warning('请先填写正确的邮箱')
    return
  }
  sending.value = true
  try {
    const res = await sendEmailCode({ email, purpose })
    if (res.channel === 'console' && res.dev_code) {
      // 开发期兜底通道：邮件没配好也能继续联调
      ElMessage.success(`验证码已回显：${res.dev_code}`)
      if (purpose === 'login') emailForm.code = res.dev_code
      else resetForm.code = res.dev_code
    } else {
      ElMessage.success('验证码已发送，请查收邮件')
    }
    startCountdown(res.resend_after || 60)
  } catch {
    // 错误提示已由响应拦截器统一处理
  } finally {
    sending.value = false
  }
}

function startCountdown(seconds: number): void {
  countdown.value = seconds
  stopTimer()
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) stopTimer()
  }, 1000)
}

function stopTimer(): void {
  if (timer) {
    clearInterval(timer)
    timer = undefined
  }
}

/** 登录成功后按 redirect 回到之前要去的页面 */
async function afterLogin(): Promise<void> {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
  await router.replace(redirect || '/')
}

async function submitPassword(): Promise<void> {
  const form = passwordFormRef.value
  if (!form) return
  const valid = await form.validate().catch(() => false)
  if (!valid) return

  if (showCaptcha.value && !passwordForm.captcha_code.trim()) {
    ElMessage.warning('请输入图形验证码')
    return
  }

  loading.value = true
  try {
    const payload: LoginPayload = {
      username: passwordForm.username,
      password: passwordForm.password,
    }
    if (showCaptcha.value) {
      payload.captcha_id = captchaId.value
      payload.captcha_code = passwordForm.captcha_code.trim()
    }
    await authStore.login(payload)
    ElMessage.success('登录成功')
    await afterLogin()
  } catch {
    // 登录失败即开启人机验证（服务端失败满 2 次后强制要求，提前展示无影响）；
    // 已展示时旧验证码已被服务端作废（一次性），必须刷新换新的
    showCaptcha.value = true
    passwordForm.captcha_code = ''
    await refreshCaptcha()
  } finally {
    loading.value = false
  }
}

async function submitEmail(): Promise<void> {
  const form = emailFormRef.value
  if (!form) return
  const valid = await form.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.loginByEmail({ ...emailForm })
    ElMessage.success('登录成功')
    await afterLogin()
  } catch {
    // 错误提示已由响应拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function submitReset(): Promise<void> {
  const form = resetFormRef.value
  if (!form) return
  const valid = await form.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    const res = await resetPassword({ ...resetForm })
    ElMessage.success(res.message)
    resetVisible.value = false
    activeTab.value = 'password'
    passwordForm.username = resetForm.email
  } catch {
    // 错误提示已由响应拦截器统一处理
  } finally {
    loading.value = false
  }
}

function goRegister(): void {
  void router.push('/register')
}

onBeforeUnmount(stopTimer)
</script>

<style scoped lang="scss">
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1f2d3d 0%, #2b3a4d 100%);
}

.login-card {
  width: 420px;
  padding: 28px 32px 20px;
  background-color: #fff;
  border-radius: 10px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
}

.login-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 12px;
}

.login-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2d3d;
}

.login-tabs {
  :deep(.el-tabs__item) {
    font-size: 14px;
  }
}

.submit-button {
  width: 100%;
  margin-top: 4px;
}

.code-row {
  display: flex;
  gap: 8px;
  width: 100%;

  :deep(.el-input) {
    flex: 1;
  }
}

.captcha-box {
  width: 132px;
  height: 42px;
  flex-shrink: 0;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    border-color: #409eff;
  }
}

.login-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 14px;
}
</style>
