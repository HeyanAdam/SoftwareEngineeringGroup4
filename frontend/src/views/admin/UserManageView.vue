<template>
  <div class="user-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-input
            v-model="keyword"
            placeholder="按登录名 / 邮箱搜索"
            clearable
            class="search-input"
            @keyup.enter="reload"
            @clear="reload"
          >
            <template #append>
              <el-button @click="reload">搜索</el-button>
            </template>
          </el-input>
        </div>
      </template>

      <el-table v-loading="loading" :data="users" size="small">
        <el-table-column prop="login_name" label="登录名" min-width="110" />
        <el-table-column prop="email" label="邮箱" min-width="180" show-overflow-tooltip />
        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="role in row.roles"
              :key="role.role_id"
              size="small"
              :type="role.role_name === '系统管理员' ? 'danger' : 'info'"
              class="role-tag"
            >
              {{ role.role_name }}
            </el-tag>
            <span v-if="row.roles.length === 0" class="empty-roles">未分配</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-permission="'user:manage'"
              :model-value="row.account_status === 1"
              :loading="statusLoading === row.user_id"
              @change="(value: boolean) => toggleStatus(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="170" />
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button
              v-permission="'user:manage'"
              link
              type="primary"
              size="small"
              @click="openAssign(row)"
            >
              分配角色
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        class="pager"
        @current-change="loadUsers"
      />
    </el-card>

    <!-- 分配角色 -->
    <el-dialog v-model="assignVisible" title="分配角色" width="460px">
      <div v-if="assignUser" class="assign-header">
        用户：<strong>{{ assignUser.login_name }}</strong>
      </div>
      <div class="role-options">
        <el-checkbox
          v-for="role in roles"
          :key="role.role_id"
          v-model="checked[role.role_id]"
          class="role-option"
        >
          <span class="role-name">{{ role.role_name }}</span>
          <span class="role-desc">{{ role.role_desc || '无描述' }}</span>
        </el-checkbox>
      </div>
      <div class="assign-tip">提示：不能修改自己的角色；管理员角色请谨慎授予。</div>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button
          v-permission="'user:manage'"
          type="primary"
          :loading="saving"
          @click="submitAssign"
        >
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listRoles, listUsers, updateUserRoles, updateUserStatus } from '@/api/rbac'
import { permission as vPermission } from '@/directives/permission'
import type { AdminUserItem, RoleItem } from '@/types/rbac'

const loading = ref(false)
const saving = ref(false)
const statusLoading = ref<number | null>(null)

const users = ref<AdminUserItem[]>([])
const roles = ref<RoleItem[]>([])
const keyword = ref('')
const page = ref(1)
const size = ref(20)
const total = ref(0)

const assignVisible = ref(false)
const assignUser = ref<AdminUserItem | null>(null)
const checked = reactive<Record<number, boolean>>({})

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    const res = await listUsers({ keyword: keyword.value || undefined, page: page.value, size: size.value })
    users.value = res.items
    total.value = res.total
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadRoles(): Promise<void> {
  try {
    roles.value = await listRoles()
  } catch {
    // 拦截器已提示
  }
}

function reload(): void {
  page.value = 1
  void loadUsers()
}

/** 启用 / 禁用账号；禁用后该用户已签发的令牌会立即被后端拒绝 */
async function toggleStatus(row: AdminUserItem, enabled: boolean): Promise<void> {
  statusLoading.value = row.user_id
  try {
    const updated = await updateUserStatus(row.user_id, enabled ? 1 : 0)
    row.account_status = updated.account_status
    ElMessage.success(enabled ? '已启用该账号' : '已禁用该账号')
  } catch {
    // 拦截器已提示
  } finally {
    statusLoading.value = null
  }
}

function openAssign(row: AdminUserItem): void {
  assignUser.value = row
  Object.keys(checked).forEach((key) => {
    delete checked[Number(key)]
  })
  row.roles.forEach((role) => {
    checked[role.role_id] = true
  })
  assignVisible.value = true
}

async function submitAssign(): Promise<void> {
  if (!assignUser.value) return
  const roleIds = Object.entries(checked)
    .filter(([, value]) => value)
    .map(([key]) => Number(key))

  saving.value = true
  try {
    const updated = await updateUserRoles(assignUser.value.user_id, roleIds)
    assignUser.value.roles = updated
    assignVisible.value = false
    ElMessage.success('角色已更新')
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadRoles()])
})
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.search-input {
  width: 280px;
}

.role-tag {
  margin-right: 6px;
}

.empty-roles {
  color: #909399;
  font-size: 12px;
}

.pager {
  margin-top: 12px;
  justify-content: flex-end;
}

.assign-header {
  margin-bottom: 10px;
  color: #606266;
}

.role-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.role-option {
  height: auto;
  align-items: flex-start;

  :deep(.el-checkbox__label) {
    display: inline-flex;
    flex-direction: column;
    line-height: 1.5;
  }
}

.role-name {
  font-size: 13px;
  color: #303133;
}

.role-desc {
  font-size: 12px;
  color: #909399;
}

.assign-tip {
  margin-top: 12px;
  color: #e6a23c;
  font-size: 12px;
}
</style>
