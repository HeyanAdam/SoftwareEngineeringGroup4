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
            <el-tag effect="plain" type="info">考研备考中</el-tag>
          </div>
          <el-descriptions :column="1" border class="account-desc">
            <el-descriptions-item label="用户名">
              {{ authStore.user?.username ?? '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="邮箱">
              {{ authStore.user?.email ?? '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <p class="account-tip">用户名与邮箱用于登录，暂不支持修改。</p>
        </el-card>
      </el-col>

      <!-- 备考信息（可编辑） -->
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
            <el-form-item label="目标院校" prop="target_school">
              <el-input v-model="form.target_school" placeholder="例如：北京邮电大学" clearable />
            </el-form-item>
            <el-form-item label="目标专业" prop="target_major">
              <el-input v-model="form.target_major" placeholder="例如：计算机科学与技术" clearable />
            </el-form-item>
            <el-form-item label="考试年份" prop="exam_year">
              <el-input v-model="form.exam_year" placeholder="例如：2027" clearable class="year-input" />
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Check } from '@element-plus/icons-vue'

import { updateProfile } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import type { UserProfile, UserUpdatePayload } from '@/types/user'

/** 表单模型：exam_year 用字符串承接 el-input，提交时再转成数字 */
interface ProfileFormModel {
  nickname: string
  target_school: string
  target_major: string
  exam_year: string
}

const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const saving = ref(false)
/** 已加载的资料，用于「重置」 */
const profile = ref<UserProfile | null>(null)

const form = reactive<ProfileFormModel>({
  nickname: '',
  target_school: '',
  target_major: '',
  exam_year: '',
})

const rules: FormRules<ProfileFormModel> = {
  nickname: [{ max: 20, message: '昵称不能超过 20 个字符', trigger: 'blur' }],
  exam_year: [
    {
      validator: (_rule, value, callback) => {
        if (typeof value !== 'string' || value.length === 0) {
          callback()
          return
        }
        const year = Number(value)
        if (!Number.isInteger(year) || year < 2000 || year > 2100) {
          callback(new Error('请输入 2000-2100 之间的年份'))
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
  form.target_school = data.target_school ?? ''
  form.target_major = data.target_major ?? ''
  form.exam_year = data.exam_year === null ? '' : String(data.exam_year)
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
    target_school: form.target_school.trim(),
    target_major: form.target_major.trim(),
  }
  if (form.exam_year.length > 0) {
    payload.exam_year = Number(form.exam_year)
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
    })
    ElMessage.success('保存成功')
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

.year-input {
  width: 180px;
}
</style>
