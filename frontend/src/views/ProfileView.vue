<template>
  <div class="profile-page">
    <el-row :gutter="20">
      <!-- 基本资料（只读） -->
      <el-col :xs="24" :md="8">
        <el-card shadow="never" class="account-card">
          <template #header>
            <span class="card-title">账号信息</span>
          </template>
          <div class="account">
            <el-avatar :size="64" class="account-avatar">{{ avatarText }}</el-avatar>
            <div class="account-name">{{ authStore.displayName }}</div>
            <el-tag v-if="authStore.isAdmin" effect="plain" type="danger">系统管理员</el-tag>
            <el-tag v-else effect="plain" type="info">考研备考中</el-tag>
          </div>
          <el-descriptions :column="1" border class="account-desc">
            <el-descriptions-item label="用户名">
              {{ authStore.user?.username ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="邮箱">
              {{ authStore.user?.email ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="角色">
              {{ authStore.roles.join('、') || '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <p class="account-tip">用户名与邮箱用于登录，暂不支持修改。</p>
          <el-button class="password-button" @click="passwordVisible = true">修改密码</el-button>
        </el-card>
      </el-col>

      <!-- 备考信息（可编辑，字段与 user_account 表一致） -->
      <el-col :xs="24" :md="16">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span class="card-title">备考信息</span>
              <el-button type="primary" :loading="saving" :disabled="loading" @click="handleSave">
                <el-icon><Check /></el-icon>
                保存
              </el-button>
            </div>
          </template>

          <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <el-form-item label="昵称" prop="nickname">
              <el-input v-model="form.nickname" placeholder="请输入昵称" clearable />
            </el-form-item>
            <el-form-item label="本科专业" prop="undergraduate_major">
              <el-input v-model="form.undergraduate_major" placeholder="例如：软件工程" clearable />
            </el-form-item>
            <el-form-item label="报考专业" prop="major">
              <el-input v-model="form.major" placeholder="例如：计算机科学与技术" clearable />
            </el-form-item>
            <el-form-item label="目标地区" prop="target_area">
              <el-input v-model="form.target_area" placeholder="例如：四川" clearable class="short-input" />
            </el-form-item>
            <el-form-item label="备考阶段" prop="prep_stage">
              <el-select v-model="form.prep_stage" placeholder="请选择当前阶段" clearable class="short-input">
                <el-option v-for="stage in PREP_STAGES" :key="stage" :label="stage" :value="stage" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标分数" prop="target_score">
              <el-input
                v-model="form.target_score"
                placeholder="例如：380"
                clearable
                class="short-input"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" :disabled="loading" @click="handleSave">
                保存修改
              </el-button>
              <el-button :disabled="loading || saving" @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 修改密码：改完旧令牌全部失效，需要重新登录 -->
    <el-dialog v-model="passwordVisible" title="修改密码" width="420px">
      <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-position="top">
        <el-form-item label="当前密码" prop="old_password">
          <el-input v-model="passwordForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="passwordForm.new_password"
            type="password"
            placeholder="至少 8 位，需包含字母和数字"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Check } from '@element-plus/icons-vue'

import { changePassword, updateProfile } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { ChangePasswordPayload, UserProfile, UserUpdatePayload } from '@/types/user'

/** 备考阶段选项（与 user_account.prep_stage 的取值一致） */
const PREP_STAGES = ['基础', '强化', '冲刺']

/** 表单模型：target_score 用字符串承接 el-input，提交时再转成数字 */
interface ProfileFormModel {
  nickname: string
  undergraduate_major: string
  major: string
  target_area: string
  prep_stage: string
  target_score: string
}

interface PasswordFormModel extends ChangePasswordPayload {
  confirm_password: string
}

const authStore = useAuthStore()
const router = useRouter()

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
/** 已加载的资料，用于「重置」 */
const profile = ref<UserProfile | null>(null)

const passwordVisible = ref(false)
const passwordFormRef = ref<FormInstance>()
const passwordForm = reactive<PasswordFormModel>({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const form = reactive<ProfileFormModel>({
  nickname: '',
  undergraduate_major: '',
  major: '',
  target_area: '',
  prep_stage: '',
  target_score: '',
})

const rules: FormRules<ProfileFormModel> = {
  nickname: [{ max: 20, message: '昵称不能超过 20 个字符', trigger: 'blur' }],
  target_score: [
    {
      validator: (_rule, value, callback) => {
        if (typeof value !== 'string' || value.length === 0) {
          callback()
          return
        }
        const score = Number(value)
        if (!Number.isInteger(score) || score < 0 || score > 1000) {
          callback(new Error('请输入 0-1000 之间的分数'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

const passwordRules: FormRules<PasswordFormModel> = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '密码长度不能少于 8 位', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value && (!/[A-Za-z]/.test(value) || !/\d/.test(value))) {
          callback(new Error('密码必须同时包含字母和数字'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value: string, callback) => {
        if (value !== passwordForm.new_password) {
          callback(new Error('两次输入的密码不一致'))
          return
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

const avatarText = computed(() => authStore.displayName.charAt(0))

/** 把后端资料回填到表单 */
function fillForm(data: UserProfile): void {
  profile.value = data
  form.nickname = data.nickname ?? ''
  form.undergraduate_major = data.undergraduate_major ?? ''
  form.major = data.major ?? ''
  form.target_area = data.target_area ?? ''
  form.prep_stage = data.prep_stage ?? ''
  form.target_score = data.target_score === null ? '' : String(data.target_score)
}

async function loadProfile(): Promise<void> {
  loading.value = true
  try {
    const data = await authStore.fetchProfile()
    if (data) {
      fillForm(data)
    }
  } catch {
    ElMessage.warning('资料获取失败，可先填写后重试保存')
  } finally {
    loading.value = false
  }
}

/** 重置为最近一次加载到的资料 */
function resetForm(): void {
  if (profile.value) {
    fillForm(profile.value)
  }
  formRef.value?.clearValidate()
}

async function handleSave(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const payload: UserUpdatePayload = {
    nickname: form.nickname.trim(),
    undergraduate_major: form.undergraduate_major.trim(),
    major: form.major.trim(),
    target_area: form.target_area.trim(),
    prep_stage: form.prep_stage,
  }
  if (form.target_score.length > 0) {
    payload.target_score = Number(form.target_score)
  }

  saving.value = true
  try {
    const updated = await updateProfile(payload)
    fillForm(updated)
    // 同步昵称到本地登录态，顶栏会立即更新
    authStore.setUser({
      id: updated.id,
      username: updated.username,
      email: updated.email,
      nickname: updated.nickname,
      roles: authStore.roles,
      permissions: authStore.permissions,
    })
    ElMessage.success('保存成功')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    saving.value = false
  }
}

async function submitPassword(): Promise<void> {
  if (!passwordFormRef.value) return
  const valid = await passwordFormRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const res = await changePassword({
      old_password: passwordForm.old_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success(res.message)
    passwordVisible.value = false
    // 改密后旧令牌在服务端已作废，本地也清掉再回登录页
    await authStore.logout()
    await router.replace('/login')
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadProfile()
})
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.account {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 8px 0 18px;
}

.account-avatar {
  background-color: #409eff;
  color: #fff;
  font-size: 24px;
}

.account-name {
  font-size: 16px;
  font-weight: 600;
}

.account-desc {
  margin-top: 4px;
}

.account-tip {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
  text-align: center;
}

.password-button {
  width: 100%;
  margin-top: 12px;
}

.short-input {
  width: 200px;
}
</style>
