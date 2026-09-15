<script setup lang="ts">
/** 角色权限管理: 角色表格 + 按模块分组的权限树 + 新建/编辑 */

import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import {
  ElAlert,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElPopconfirm,
  ElTable,
  ElTableColumn,
  ElTag,
  ElTree,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'

import PageContainer from '@/components/common/PageContainer.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { createRole, deleteRole, listPermissions, listRoles, updateRole } from '@/api/role'
import { useAppStore } from '@/stores/app'
import { useAuthStore } from '@/stores/auth'
import { formatDateTime } from '@/utils/format'
import { moduleLabel } from '@/utils/permission'
import type { PermissionOut } from '@/types/common'
import type { PermissionModuleGroup, Role, RoleCreatePayload, RoleUpdatePayload } from '@/types/role'

/** el-tree 节点 */
interface TreeNode {
  id: string
  label: string
  module: string
  children?: TreeNode[]
}

const authStore = useAuthStore()
const appStore = useAppStore()

const loading = ref(false)
const roles = ref<Role[]>([])
const permissions = ref<PermissionOut[]>([])
const errorMessage = ref('')

/** 权限树数据 (按 module 分组) */
const treeData = computed<TreeNode[]>(() => {
  const groups = new Map<string, PermissionModuleGroup>()
  for (const item of permissions.value) {
    const group = groups.get(item.module) ?? {
      module: item.module,
      label: moduleLabel(item.module),
      children: [],
    }
    group.children.push(item)
    groups.set(item.module, group)
  }
  return [...groups.values()].map((group) => ({
    id: `module:${group.module}`,
    label: group.label,
    module: group.module,
    children: group.children.map((item) => ({
      id: item.code,
      label: `${item.name} (${item.code})`,
      module: item.module,
    })),
  }))
})

const permissionCount = computed(() => permissions.value.length)

/* ------------------------------- 弹窗 ------------------------------- */
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const treeRef = ref<InstanceType<typeof ElTree>>()

const form = reactive({
  code: '',
  name: '',
  description: '',
})

const dialogTitle = computed(() => (dialogMode.value === 'create' ? '新建角色' : '编辑角色'))

const rules: FormRules<typeof form> = {
  code: [
    { required: true, message: '请输入角色编码', trigger: 'blur' },
    {
      pattern: /^[a-z][a-z0-9_:.-]{1,63}$/,
      message: '小写字母开头, 2-64 位 (小写字母/数字/下划线/冒号/点/短横线)',
      trigger: 'blur',
    },
  ],
  name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }],
}

function resetForm(): void {
  form.code = ''
  form.name = ''
  form.description = ''
  editingId.value = null
  formRef.value?.clearValidate()
  void nextTick(() => treeRef.value?.setCheckedKeys([]))
}

async function openCreate(): Promise<void> {
  dialogMode.value = 'create'
  resetForm()
  dialogVisible.value = true
}

async function openEdit(row: unknown): Promise<void> {
  const role = asRole(row)
  dialogMode.value = 'edit'
  resetForm()
  editingId.value = role.id
  form.code = role.code
  form.name = role.name
  form.description = role.description ?? ''
  dialogVisible.value = true
  await nextTick()
  treeRef.value?.setCheckedKeys(role.permissions, false)
}

/** 收集权限树中已勾选的叶子权限码 */
function collectCheckedPermissions(): string[] {
  const tree = treeRef.value
  if (!tree) return []
  const checked = tree.getCheckedKeys(false) as string[]
  const half = tree.getHalfCheckedKeys() as string[]
  return [...checked, ...half].filter((key) => !key.startsWith('module:'))
}

async function submitForm(): Promise<void> {
  const instance = formRef.value
  if (!instance) return
  const valid = await instance.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const permissionCodes = collectCheckedPermissions()
    if (dialogMode.value === 'create') {
      const payload: RoleCreatePayload = {
        code: form.code.trim(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        permissions: permissionCodes,
      }
      await createRole(payload)
      ElMessage.success('角色创建成功')
    } else if (editingId.value !== null) {
      const payload: RoleUpdatePayload = {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        permissions: permissionCodes,
      }
      await updateRole(editingId.value, payload)
      ElMessage.success('角色更新成功')
      // 若改的是当前用户所属角色, 刷新自身权限
      if (authStore.roles.includes(form.code)) await authStore.fetchProfile()
    }
    dialogVisible.value = false
    await load()
  } finally {
    submitting.value = false
  }
}

/**
 * el-table-column 作用域插槽的行类型为 DefaultRow, 无法自动收窄为 Role,
 * 这里集中做一次类型收口。
 */
function asRole(row: unknown): Role {
  return row as Role
}

async function handleDelete(row: unknown): Promise<void> {
  await deleteRole(asRole(row).id)
  ElMessage.success('角色已删除')
  await load()
}

async function load(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const [roleList, permissionList] = await Promise.all([listRoles(), listPermissions()])
    roles.value = roleList
    permissions.value = permissionList
  } catch (error) {
    errorMessage.value = (error as { message?: string })?.message ?? '角色数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  appStore.pageLoading = true
  void load().finally(() => {
    appStore.pageLoading = false
  })
})
</script>

<template>
  <PageContainer title="角色权限" description="维护角色及其权限点, 内置角色不可删除">
    <template #actions>
      <ElButton :icon="Refresh" :loading="loading" @click="load()">刷新</ElButton>
      <ElButton v-permission="'roles:write'" type="primary" :icon="Plus" @click="openCreate">
        新建角色
      </ElButton>
    </template>

    <ElAlert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="mb-16"
    />

    <ElTable v-loading="loading" :data="roles" border stripe row-key="id">
      <template #empty>
        <EmptyState description="暂无角色数据" />
      </template>

      <ElTableColumn prop="code" label="角色编码" width="160">
        <template #default="{ row }">
          <span class="text-mono">{{ row.code }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn prop="name" label="名称" width="140" />

      <ElTableColumn prop="description" label="描述" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <span class="text-secondary">{{ row.description || '-' }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="权限点" min-width="260">
        <template #default="{ row }">
          <div class="permission-tags">
            <ElTag size="small" effect="light" type="info">
              共 {{ row.permissions.length }} 项
            </ElTag>
            <ElTag
              v-for="code in row.permissions.slice(0, 4)"
              :key="code"
              size="small"
              effect="plain"
            >
              {{ code }}
            </ElTag>
            <span v-if="row.permissions.length > 4" class="text-muted">
              +{{ row.permissions.length - 4 }}
            </span>
          </div>
        </template>
      </ElTableColumn>

      <ElTableColumn label="类型" width="100" align="center">
        <template #default="{ row }">
          <ElTag :type="row.is_builtin ? 'warning' : 'success'" size="small" effect="light">
            {{ row.is_builtin ? '内置' : '自定义' }}
          </ElTag>
        </template>
      </ElTableColumn>

      <ElTableColumn label="更新时间" width="180">
        <template #default="{ row }">
          <span class="text-secondary">{{ formatDateTime(row.updated_at) }}</span>
        </template>
      </ElTableColumn>

      <ElTableColumn label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <div class="row-actions">
            <ElButton
              v-permission="'roles:write'"
              link
              type="primary"
              :icon="Edit"
              @click="openEdit(row)"
            >
              编辑
            </ElButton>
            <ElPopconfirm
              v-permission="'roles:write'"
              :title="`确定删除角色「${row.name}」吗?`"
              confirm-button-text="删除"
              cancel-button-text="取消"
              confirm-button-type="danger"
              width="240"
              :disabled="row.is_builtin"
              @confirm="handleDelete(row)"
            >
              <template #reference>
                <ElButton link type="danger" :icon="Delete" :disabled="row.is_builtin">
                  删除
                </ElButton>
              </template>
            </ElPopconfirm>
          </div>
        </template>
      </ElTableColumn>
    </ElTable>

    <ElDialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="620px"
      destroy-on-close
      @closed="resetForm"
    >
      <ElForm ref="formRef" :model="form" :rules="rules" label-width="90px">
        <ElFormItem label="角色编码" prop="code">
          <ElInput
            v-model="form.code"
            :disabled="dialogMode === 'edit'"
            placeholder="例如: content_manager"
          />
        </ElFormItem>
        <ElFormItem label="角色名称" prop="name">
          <ElInput v-model="form.name" placeholder="例如: 内容管理员" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput
            v-model="form.description"
            type="textarea"
            :rows="2"
            maxlength="255"
            show-word-limit
            placeholder="角色职责说明"
          />
        </ElFormItem>
        <ElFormItem label="权限点">
          <div class="permission-tree">
            <div class="permission-tree__header">
              <span class="text-secondary">共 {{ permissionCount }} 个权限点, 勾选后随角色一并保存</span>
            </div>
            <ElTree
              ref="treeRef"
              :data="treeData"
              show-checkbox
              node-key="id"
              default-expand-all
              :props="{ label: 'label', children: 'children' }"
              class="permission-tree__body"
            />
          </div>
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
.permission-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
}

.row-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.permission-tree {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--app-border-color);
  border-radius: var(--app-radius-sm);

  &__header {
    padding-bottom: 8px;
    margin-bottom: 6px;
    font-size: 12px;
    border-bottom: 1px dashed var(--app-border-color-light);
  }

  &__body {
    max-height: 300px;
    overflow-y: auto;
  }
}
</style>
