<template>
  <div class="role-page">
    <el-row :gutter="16">
      <!-- 左：角色列表 -->
      <el-col :span="9">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>角色列表</span>
              <el-button
                v-permission="'role:manage'"
                type="primary"
                size="small"
                @click="openCreate"
              >
                新增角色
              </el-button>
            </div>
          </template>

          <el-table
            v-loading="loading"
            :data="roles"
            highlight-current-row
            size="small"
            @current-change="handleSelectRole"
          >
            <el-table-column prop="role_name" label="角色名称" min-width="110">
              <template #default="{ row }">
                <span>{{ row.role_name }}</span>
                <el-tag v-if="row.built_in" size="small" type="info" class="built-tag">内置</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="user_count" label="用户数" width="70" align="center" />
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button
                  v-permission="'role:manage'"
                  link
                  type="primary"
                  size="small"
                  @click.stop="openEdit(row)"
                >
                  编辑
                </el-button>
                <el-button
                  v-permission="'role:manage'"
                  link
                  type="danger"
                  size="small"
                  :disabled="row.built_in"
                  @click.stop="handleDelete(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-empty v-if="!loading && roles.length === 0" description="还没有角色" :image-size="70" />
        </el-card>
      </el-col>

      <!-- 右：权限勾选 -->
      <el-col :span="15">
        <el-card shadow="never">
          <template #header>
            <div class="card-header">
              <span>
                权限配置
                <el-tag v-if="selectedRole" size="small" class="role-tag">{{ selectedRole.role_name }}</el-tag>
              </span>
              <el-button
                v-permission="'role:manage'"
                type="primary"
                size="small"
                :disabled="!selectedRole"
                :loading="saving"
                @click="savePermissions"
              >
                保存授权
              </el-button>
            </div>
          </template>

          <el-empty v-if="!selectedRole" description="请先在左侧选择一个角色" :image-size="80" />

          <div v-else class="perm-groups">
            <div v-for="group in permissionGroups" :key="group.module_name" class="perm-group">
              <div class="perm-group-header">
                <span class="module-name">{{ group.module_name }}</span>
                <span class="module-actions">
                  <el-button link type="primary" size="small" @click="checkAll(group)">全选</el-button>
                  <el-button link size="small" @click="clearGroup(group)">清空</el-button>
                </span>
              </div>
              <div class="perm-items">
                <el-checkbox
                  v-for="perm in group.permissions"
                  :key="perm.perm_id"
                  v-model="checked[perm.perm_id]"
                  class="perm-item"
                >
                  <span class="perm-name">{{ perm.perm_name }}</span>
                  <span class="perm-key">{{ perm.perm_key }}</span>
                </el-checkbox>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 新增 / 编辑角色 -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑角色' : '新增角色'" width="420px">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top">
        <el-form-item label="角色名称" prop="role_name">
          <el-input v-model="form.role_name" placeholder="2-30 个字符，不可重名" maxlength="30" />
        </el-form-item>
        <el-form-item label="角色描述" prop="role_desc">
          <el-input
            v-model="form.role_desc"
            type="textarea"
            :rows="3"
            placeholder="这个角色负责什么，留空也可以"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

import {
  createRole,
  deleteRole,
  getRolePermissions,
  listPermissions,
  listRoles,
  updateRole,
  updateRolePermissions,
} from '@/api/rbac'
import { permission as vPermission } from '@/directives/permission'
import type { PermissionGroup, RoleItem, RolePayload } from '@/types/rbac'

const loading = ref(false)
const saving = ref(false)
const roles = ref<RoleItem[]>([])
const permissionGroups = ref<PermissionGroup[]>([])
const selectedRole = ref<RoleItem | null>(null)

/** 用 id -> boolean 的映射保存勾选状态，避免依赖 el-checkbox 的 value/label 版本差异 */
const checked = reactive<Record<number, boolean>>({})

const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive<RolePayload>({ role_name: '', role_desc: '' })

const formRules: FormRules = {
  role_name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 2, max: 30, message: '长度在 2 到 30 个字符', trigger: 'blur' },
  ],
  role_desc: [{ max: 200, message: '最多 200 个字符', trigger: 'blur' }],
}

async function loadRoles(): Promise<void> {
  loading.value = true
  try {
    roles.value = await listRoles()
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}

async function loadGroups(): Promise<void> {
  try {
    permissionGroups.value = await listPermissions()
  } catch {
    // 拦截器已提示
  }
}

/** 选中角色后拉取该角色的权限并回填勾选状态 */
async function handleSelectRole(row: RoleItem | null): Promise<void> {
  if (!row) return
  selectedRole.value = row
  Object.keys(checked).forEach((key) => {
    delete checked[Number(key)]
  })
  try {
    const permIds = await getRolePermissions(row.role_id)
    permIds.forEach((id) => {
      checked[id] = true
    })
  } catch {
    // 拦截器已提示
  }
}

function checkAll(group: PermissionGroup): void {
  group.permissions.forEach((perm) => {
    checked[perm.perm_id] = true
  })
}

function clearGroup(group: PermissionGroup): void {
  group.permissions.forEach((perm) => {
    checked[perm.perm_id] = false
  })
}

async function savePermissions(): Promise<void> {
  if (!selectedRole.value) return
  const permIds = Object.entries(checked)
    .filter(([, value]) => value)
    .map(([key]) => Number(key))

  saving.value = true
  try {
    await updateRolePermissions(selectedRole.value.role_id, permIds)
    ElMessage.success('授权已保存')
    await loadRoles()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

function openCreate(): void {
  editingId.value = null
  form.role_name = ''
  form.role_desc = ''
  dialogVisible.value = true
}

function openEdit(row: RoleItem): void {
  editingId.value = row.role_id
  form.role_name = row.role_name
  form.role_desc = row.role_desc ?? ''
  dialogVisible.value = true
}

async function submitForm(): Promise<void> {
  const instance = formRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (editingId.value) {
      await updateRole(editingId.value, { ...form })
      ElMessage.success('角色已更新')
    } else {
      await createRole({ ...form })
      ElMessage.success('角色已创建')
    }
    dialogVisible.value = false
    await loadRoles()
  } catch {
    // 拦截器已提示
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: RoleItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除角色「${row.role_name}」吗？该角色下的用户需要先解除分配。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await deleteRole(row.role_id)
    ElMessage.success('角色已删除')
    if (selectedRole.value?.role_id === row.role_id) selectedRole.value = null
    await loadRoles()
  } catch {
    // 拦截器已提示
  }
}

onMounted(async () => {
  await Promise.all([loadRoles(), loadGroups()])
})
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.built-tag {
  margin-left: 6px;
}

.role-tag {
  margin-left: 8px;
}

.perm-groups {
  max-height: calc(100vh - 230px);
  overflow-y: auto;
}

.perm-group {
  padding: 10px 0;
  border-bottom: 1px dashed #ebeef5;

  &:last-child {
    border-bottom: none;
  }
}

.perm-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.module-name {
  font-weight: 600;
  color: #303133;
}

.perm-items {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
}

.perm-item {
  margin-right: 0;

  :deep(.el-checkbox__label) {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
  }
}

.perm-name {
  font-size: 13px;
}

.perm-key {
  color: #909399;
  font-size: 12px;
}
</style>
