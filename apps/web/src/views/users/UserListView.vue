<script setup lang="ts">
/** 用户管理: 表格 + 分页 + 筛选 + 新建/编辑 + 角色分配 + 启用禁用 + 重置密码 + 删除 */

import { computed, onMounted, reactive, ref } from 'vue'
import {
  ElAvatar,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElMessageBox,
  ElOption,
  ElPagination,
  ElPopconfirm,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTooltip,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Delete, Edit, Key, Plus, Refresh, Search } from '@element-plus/icons-vue'

import PageContainer from '@/components/common/PageContainer.vue'
import SearchToolbar from '@/components/common/SearchToolbar.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import {
  assignRoles,
  createUser,
  deleteUser,
  getRoleOptions,
  listUsers,
  resetUserPassword,
  toggleUserActive,
  updateUser,
} from '@/api/user'
import { useTable } from '@/composables/useTable'
import { formatDateTime, initialsOf } from '@/utils/format'
import type { Role } from '@/types/role'
import type { UserCreatePayload, UserListItem, UserUpdatePayload } from '@/types/user'

interface UserFilters {
  keyword: string
  is_active: '' | 'true' | 'false'
  role: string
}

const roleOptions = ref<Role[]>([])

const { rows, total, loading, query, load, search, reset, changePage, changePageSize } = useTable<
  UserListItem,
  UserFilters
>(
  (params) =>
    listUsers({
      page: params.page,
      page_size: params.page_size,
      sort_by: params.sort_by,
      keyword: params.filters.keyword || undefined,
      is_active:
        params.filters.is_active === '' ? undefined : params.filters.is_active === 'true',
      role: params.filters.role || undefined,
    }),
  {
    pageSize: 10,
    sortBy: '-created_at',
    filters: { keyword: '', is_active: '', role: '' },
  },
)

/* ------------------------------- 编辑弹窗 ------------------------------- */
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  email: '',
  full_name: '',
  password: '',
  is_active: true,
  role_codes: [] as string[],
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建用户' : '编辑用户'))

/** 密码校验: 至少 8 位且同时包含字母与数字 */
function validatePassword(_rule: unknown, value: string, callback: (error?: Error) => void): void {
  if (dialogMode.value === 'edit' && !value) return callback()
  if (!value) return callback(new Error('请输入初始密码'))
  if (value.length < 8) return callback(new Error('密码至少 8 位'))
  if (!/[A-Za-z]/.test(value) || !/\d/.test(value)) {
    return callback(new Error('密码需同时包含字母和数字'))
  }
  return callback()
}

const rules = computed<FormRules<typeof form>>(() => ({
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
  password: [{ required: dialogMode.value === 'create', validator: validatePassword, trigger: 'blur' }],
}))

function resetForm(): void {
  form.username = ''
  form.email = ''
  form.full_name = ''
  form.password = ''
  form.is_active = true
  form.role_codes = []
  editingId.value = null
  formRef.value?.clearValidate()
}

function openCreate(): void {
  dialogMode.value = 'create'
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: unknown): void {
  const user = asUser(row)
  dialogMode.value = 'edit'
  resetForm()
  editingId.value = user.id
  form.username = user.username
  form.email = user.email
  form.full_name = user.full_name ?? ''
  form.is_active = user.is_active
  form.role_codes = [...user.roles]
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const instance = formRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const payload: UserCreatePayload = {
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        full_name: form.full_name.trim() || undefined,
        is_active: form.is_active,
        roles: form.role_codes,
      }
      await createUser(payload)
      ElMessage.success('用户创建成功')
    } else if (editingId.value !== null) {
      const payload: UserUpdatePayload = {
        email: form.email.trim(),
        full_name: form.full_name.trim() || undefined,
        is_active: form.is_active,
      }
      await updateUser(editingId.value, payload)
      await assignRoles(editingId.value, { role_codes: form.role_codes })
      ElMessage.success('用户更新成功')
    }
    dialogVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

/* ------------------------------- 行操作 ------------------------------- */

/**
 * el-table-column 的作用域插槽行类型为 DefaultRow (Record<PropertyKey, any>),
 * 无法自动收窄为 UserListItem, 这里集中做一次类型收口。
 */
function asUser(row: unknown): UserListItem {
  return row as UserListItem
}

async function handleToggleActive(row: unknown): Promise<void> {
  const user = asUser(row)
  const result = await toggleUserActive(user.id)
  ElMessage.success(result.is_active ? '账号已启用' : '账号已禁用')
  await load()
}

async function handleResetPassword(row: unknown): Promise<void> {
  const user = asUser(row)
  try {
    await ElMessageBox.confirm(
      `确定重置用户「${user.username}」的密码吗? 旧密码将立即失效。`,
      '重置密码',
      { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  const { password } = await resetUserPassword(user.id)
  await ElMessageBox.alert(
    `用户「${user.username}」的新密码: ${password}\n\n请立即通过安全渠道告知用户, 该密码仅显示一次。`,
    '重置成功',
    { confirmButtonText: '我已记录' },
  )
}

async function handleDelete(row: unknown): Promise<void> {
  await deleteUser(asUser(row).id)
  ElMessage.success('用户已删除')
  await load()
}

async function loadRoles(): Promise<void> {
  roleOptions.value = await getRoleOptions()
}

onMounted(async () => {
  await Promise.all([load(), loadRoles().catch(() => undefined)])
})
</script>

<template>
  <PageContainer title="用户管理" description="管理平台账号、角色与状态">
    <template #actions>
      <ElButton :icon="Refresh" :loading="loading" @click="load()">刷新</ElButton>
      <ElButton v-permission="'users:write'" type="primary" :icon="Plus" @click="openCreate">
        新建用户
      </ElButton>
    </template>

    <SearchToolbar>
      <ElInput
        v-model="query.filters.keyword"
        placeholder="搜索用户名 / 邮箱 / 姓名"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search()"
        @clear="search()"
      />
      <ElSelect v-model="query.filters.is_active" placeholder="账号状态" clearable>
        <ElOption label="全部状态" value="" />
        <ElOption label="已启用" value="true" />
        <ElOption label="已禁用" value="false" />
      </ElSelect>
      <ElSelect v-model="query.filters.role" placeholder="角色" clearable>
        <ElOption label="全部角色" value="" />
        <ElOption v-for="role in roleOptions" :key="role.code" :label="role.name" :value="role.code" />
      </ElSelect>
      <template #actions>
        <ElButton type="primary" :icon="Search" @click="search()">查询</ElButton>
        <ElButton @click="reset()">重置</ElButton>
      </template>
    </SearchToolbar>

    <ElTable v-loading="loading" :data="rows" border stripe row-key="id" class="user-table">
      <template #empty>
        <EmptyState description="暂无用户数据" action-text="新建用户" @action="openCreate" />
      </template>

      <ElTableColumn label="用户" min-width="220">
        <template #default="{ row }">
          <div class="user-cell">
            <ElAvatar :size="34" :src="row.avatar ?? undefined">
              {{ initialsOf(row.full_name || row.username) }}
            </ElAvatar>
            <div class="user-cell__meta">
              <span class="user-cell__name">{{ row.full_name || row.username }}</span>
              <span class="user-cell__account">@{{ row.username }}</span>
            </div>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn prop="email" label="邮箱" min-width="200" show-overflow-tooltip />

      <ElTableColumn label="角色" min-width="200">
        <template #default="{ row }">
          <div class="role-tags">
            <ElTag
              v-for="code in row.roles"
              :key="code"
              size="small"
              effect="light"
              :type="code === 'super_admin' ? 'danger' : 'primary'"
            >
              {{ roleOptions.find((item) => item.code === code)?.name ?? code }}
            </ElTag>
            <span v-if="!row.roles.length" class="text-muted">未分配</span>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="状态" width="110" align="center">
        <template #default="{ row }">
          <ElTag :type="row.is_active ? 'success' : 'info'" size="small" effect="light">
            {{ row.is_active ? '已启用' : '已禁用' }}
          </ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn label="超级管理员" width="120" align="center">
        <template #default="{ row }">
          <ElTag v-if="row.is_superuser" type="danger" size="small" effect="dark">是</ElTag>
          <span v-else class="text-muted">否</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="最近登录" width="180">
        <template #default="{ row }">
          <span class="text-secondary">{{ formatDateTime(row.last_login_at) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="创建时间" width="180">
        <template #default="{ row }">
          <span class="text-secondary">{{ formatDateTime(row.created_at) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <ElButton
              v-permission="'users:write'"
              link
              type="primary"
              :icon="Edit"
              @click="openEdit(row)"
            >
              编辑
            </ElButton>

            <ElTooltip :content="row.is_active ? '禁用账号' : '启用账号'" placement="top">
              <ElSwitch
                v-permission="'users:write'"
                :model-value="row.is_active"
                size="small"
                @change="handleToggleActive(row)"
              />
            </ElTooltip>

            <ElButton
              v-permission="'users:write'"
              link
              type="warning"
              :icon="Key"
              @click="handleResetPassword(row)"
            >
              重置密码
            </ElButton>

            <ElPopconfirm
              v-permission="'users:delete'"
              title="确定删除该用户吗?"
              confirm-button-text="删除"
              cancel-button-text="取消"
              confirm-button-type="danger"
              width="220"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <ElButton link type="danger" :icon="Delete">删除</ElButton>
              </template>
            </ElPopconfirm>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <div class="user-pagination">
      <ElPagination
        :current-page="query.page"
        :page-size="query.page_size"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        background
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="changePage"
        @size-change="changePageSize"
      />
    </div>

    <ElDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="560px"
      destroy-on-close
      @closed="resetForm"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="96px">
        <ElFormItem label="用户名" prop="username">
          <ElInput
            v-model="form.username"
            :disabled="dialogMode === 'edit'"
            placeholder="登录账号, 创建后不可修改"
          />
        </ElFormItem>
        <ElFormItem label="邮箱" prop="email">
          <ElInput v-model="form.email" placeholder="you@example.com" />
        </ElFormItem>
        <ElFormItem label="姓名" prop="full_name">
          <ElInput v-model="form.full_name" placeholder="可选" />
        </ElFormItem>
        <ElFormItem v-if="dialogMode === 'create'" label="初始密码" prop="password">
          <ElInput
            v-model="form.password"
            type="password"
            show-password
            placeholder="至少 8 位, 含字母与数字"
          />
        </ElFormItem>
        <ElFormItem label="角色" prop="role_codes">
          <ElSelect v-model="form.role_codes" multiple collapse-tags placeholder="请选择角色">
            <ElOption
              v-for="role in roleOptions"
              :key="role.code"
              :label="`${role.name} (${role.code})`"
              :value="role.code"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="账号状态">
          <ElSwitch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </ElFormItem>
      </ElForm>

      <template #footer>
        <ElButton @click="dialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="submitting" @click="submitForm">保存</ElButton>
      </template>
    </ElDialog>
  </PageContainer>
</template>

<style scoped lang="scss">
.user-table {
  width: 100%;
}

.user-cell {
  display: flex;
  gap: 10px;
  align-items: center;

  &__meta {
    display: flex;
    flex-direction: column;
    line-height: 1.3;
  }

  &__name {
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__account {
    font-size: 12px;
    color: var(--app-text-placeholder);
  }
}

.role-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.row-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.user-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
