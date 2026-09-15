<script setup lang="ts">
/** 个人中心: 资料编辑 + 修改密码 */

import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElAlert,
  ElAvatar,
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElTag,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Lock, Message, Phone, UserFilled } from '@element-plus/icons-vue'

import PageContainer from '@/components/common/PageContainer.vue'
import { useAuthStore } from '@/stores/auth'
import { useWsStore } from '@/stores/ws'
import { formatDateTime, initialsOf } from '@/utils/format'

const authStore = useAuthStore()
const wsStore = useWsStore()
const router = useRouter()

const profileRef = ref<FormInstance>()
const passwordRef = ref<FormInstance>()
const savingProfile = ref(false)
const savingPassword = ref(false)

const profileForm = reactive({
  email: '',
  full_name: '',
  phone: '',
})

const passwordForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const user = computed(() => authStore.user)

const profileRules: FormRules<typeof profileForm> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  full_name: [{ max: 64, message: '姓名不能超过 64 个字符', trigger: 'blur' }],
  phone: [{ max: 32, message: '手机号不能超过 32 个字符', trigger: 'blur' }],
}

/** 新密码校验: 与后端一致 (>=8 位且含字母与数字) */
function validateNewPassword(
  _rule: unknown,
  value: string,
  callback: (error?: Error) => void,
): void {
  if (!value) return callback(new Error('请输入新密码'))
  if (value.length < 8) return callback(new Error('密码至少 8 位'))
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    return callback(new Error('密码需同时包含字母和数字'))
  }
  return callback()
}

function validateConfirm(
  _rule: unknown,
  value: string,
  callback: (error?: Error) => void,
): void {
  if (!value) return callback(new Error('请再次输入新密码'))
  if (value !== passwordForm.new_password) return callback(new Error('两次输入的密码不一致'))
  return callback()
}

const passwordRules: FormRules<typeof passwordForm> = {
  old_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [{ required: true, validator: validateNewPassword, trigger: 'blur' }],
  confirm_password: [{ required: true, validator: validateConfirm, trigger: 'blur' }],
}

function syncFormFromUser(): void {
  profileForm.email = user.value?.email ?? ''
  profileForm.full_name = user.value?.full_name ?? ''
  profileForm.phone = user.value?.phone ?? ''
}

async function saveProfile(): Promise<void> {
  const instance = profileRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  savingProfile.value = true
  try {
    await authStore.updateProfile({
      email: profileForm.email.trim(),
      full_name: profileForm.full_name.trim() || undefined,
      phone: profileForm.phone.trim() || undefined,
    })
    ElMessage.success('资料已更新')
  } finally {
    savingProfile.value = false
  }
}

async function savePassword(): Promise<void> {
  const instance = passwordRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  savingPassword.value = true
  try {
    await authStore.changePassword(passwordForm.old_password, passwordForm.new_password)
    ElMessage.success('密码已更新, 请重新登录')
    // 后端会使旧令牌失效, 前端主动清理并跳转登录
    wsStore.disconnect()
    authStore.reset()
    await router.replace({ path: '/login' })
  } finally {
    savingPassword.value = false
  }
}

onMounted(async () => {
  if (!authStore.user) await authStore.fetchProfile()
  syncFormFromUser()
})
</script>

<template>
  <PageContainer title="个人中心" description="维护个人资料与登录密码">
    <div class="profile">
      <ElCard shadow="never" class="profile__summary">
        <div class="profile__identity">
          <ElAvatar :size="64" :src="user?.avatar ?? undefined">
            {{ initialsOf(authStore.displayName) }}
          </ElAvatar>
          <div class="profile__identity-meta">
            <h3>{{ authStore.displayName }}</h3>
            <span class="text-secondary">@{{ user?.username ?? '-' }}</span>
            <div class="profile__tags">
              <ElTag
                v-for="role in authStore.roles"
                :key="role"
                size="small"
                effect="light"
                :type="role === 'super_admin' ? 'danger' : 'primary'"
              >
                {{ role }}
              </ElTag>
              <ElTag v-if="!authStore.roles.length" size="small" type="info">未分配角色</ElTag>
            </div>
          </div>
        </div>

        <ElDescriptions :column="1" border size="small" class="profile__descriptions">
          <ElDescriptionsItem label="用户 ID">{{ user?.id ?? '-' }}</ElDescriptionsItem>
          <ElDescriptionsItem label="账号状态">
            <ElTag :type="user?.is_active ? 'success' : 'info'" size="small" effect="light">
              {{ user?.is_active ? '已启用' : '已禁用' }}
            </ElTag>
          </ElDescriptionsItem>
          <ElDescriptionsItem label="超级管理员">
            {{ user?.is_superuser ? '是' : '否' }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="最近登录">
            {{ formatDateTime(user?.last_login_at) }}
          </ElDescriptionsItem>
          <ElDescriptionsItem label="权限点数量">
            {{ authStore.permissions.length }}
          </ElDescriptionsItem>
        </ElDescriptions>
      </ElCard>

      <div class="profile__forms">
        <ElCard shadow="never">
          <template #header>
            <span class="profile__card-title">基础资料</span>
          </template>
          <ElForm ref="profileRef" :model="profileForm" :rules="profileRules" label-width="90px">
            <ElFormItem label="用户名">
              <ElInput :model-value="user?.username ?? ''" disabled />
            </ElFormItem>
            <ElFormItem label="邮箱" prop="email">
              <ElInput
                v-model="profileForm.email"
                :prefix-icon="Message"
                placeholder="you@example.com"
              />
            </ElFormItem>
            <ElFormItem label="姓名" prop="full_name">
              <ElInput v-model="profileForm.full_name" :prefix-icon="UserFilled" placeholder="可选" />
            </ElFormItem>
            <ElFormItem label="手机号" prop="phone">
              <ElInput v-model="profileForm.phone" :prefix-icon="Phone" placeholder="可选" />
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" :loading="savingProfile" @click="saveProfile">
                保存资料
              </ElButton>
              <ElButton @click="syncFormFromUser">还原</ElButton>
            </ElFormItem>
          </ElForm>
        </ElCard>

        <ElCard shadow="never">
          <template #header>
            <span class="profile__card-title">修改密码</span>
          </template>

          <ElAlert
            type="warning"
            show-icon
            :closable="false"
            title="修改密码后当前登录状态会失效, 需要使用新密码重新登录。"
            class="mb-16"
          />

          <ElForm
            ref="passwordRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="90px"
          >
            <ElFormItem label="当前密码" prop="old_password">
              <ElInput
                v-model="passwordForm.old_password"
                type="password"
                show-password
                :prefix-icon="Lock"
                placeholder="请输入当前密码"
              />
            </ElFormItem>
            <ElFormItem label="新密码" prop="new_password">
              <ElInput
                v-model="passwordForm.new_password"
                type="password"
                show-password
                :prefix-icon="Lock"
                placeholder="至少 8 位, 含字母与数字"
              />
            </ElFormItem>
            <ElFormItem label="确认新密码" prop="confirm_password">
              <ElInput
                v-model="passwordForm.confirm_password"
                type="password"
                show-password
                :prefix-icon="Lock"
                placeholder="请再次输入新密码"
              />
            </ElFormItem>
            <ElFormItem>
              <ElButton type="primary" :loading="savingPassword" @click="savePassword">
                更新密码
              </ElButton>
            </ElFormItem>
          </ElForm>
        </ElCard>
      </div>
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.profile {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;

  &__identity {
    display: flex;
    gap: 14px;
    align-items: center;
    padding-bottom: 16px;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--app-border-color-light);
  }

  &__identity-meta {
    display: flex;
    flex-direction: column;
    gap: 4px;

    h3 {
      font-size: 17px;
      font-weight: 600;
      color: var(--app-text-primary);
    }
  }

  &__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 2px;
  }

  &__forms {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  &__card-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--app-text-primary);
  }
}

@media (width <= 1000px) {
  .profile {
    grid-template-columns: 1fr;
  }
}
</style>
