<template>
  <div class="audit-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>审计日志</span>
          <div class="filters">
            <el-select
              v-model="query.action"
              placeholder="全部动作"
              clearable
              class="action-select"
              @change="handleSearch"
            >
              <el-option
                v-for="item in ACTION_OPTIONS"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button
              v-permission="'role:manage'"
              :loading="loading"
              @click="handleSearch"
            >
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="items" size="small" border>
        <el-table-column prop="create_time" label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column prop="login_name" label="操作人" width="130">
          <template #default="{ row }">{{ row.login_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="180">
          <template #default="{ row }">
            <el-tag size="small" :type="row.success ? 'success' : 'danger'" effect="plain">
              {{ ACTION_LABELS[row.action] || row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_type" label="对象" width="110">
          <template #default="{ row }">
            {{ row.target_type ? `${row.target_type} #${row.target_id ?? '-'}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="260">
          <template #default="{ row }">
            <span class="detail">{{ formatDetail(row.detail) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130">
          <template #default="{ row }">{{ row.ip || '-' }}</template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @size-change="handleSearch"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listAuditLogs } from '@/api/rbac'
import { permission as vPermission } from '@/directives/permission'
import type { AuditLogItem } from '@/types/rbac'

/** 动作标识 → 中文label，与后端 write_audit 里的 action 一一对应 */
const ACTION_LABELS: Record<string, string> = {
  'user.register': '注册',
  'login.success': '登录成功',
  'login.failure': '登录失败',
  logout: '退出登录',
  'password.reset': '重置密码',
  'password.change': '修改密码',
  'role.create': '新增角色',
  'role.update': '修改角色',
  'role.delete': '删除角色',
  'role.permission.update': '角色授权',
  'user.role.update': '分配角色',
  'user.status.update': '账号启停',
}

const ACTION_OPTIONS = Object.entries(ACTION_LABELS).map(([value, label]) => ({ value, label }))

const loading = ref(false)
const items = ref<AuditLogItem[]>([])
const total = ref(0)

const query = reactive<{ action?: string; page: number; size: number }>({
  action: undefined,
  page: 1,
  size: 20,
})

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19)
}

/** detail 是后端存的 JSON，这里压成一行，避免表格被撑开 */
function formatDetail(detail: Record<string, unknown> | null): string {
  if (!detail || Object.keys(detail).length === 0) return '-'
  return JSON.stringify(detail)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await listAuditLogs({
      action: query.action,
      page: query.page,
      size: query.size,
    })
    items.value = data.items
    total.value = data.total
  } catch {
    ElMessage.warning('审计日志获取失败')
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  query.page = 1
  void load()
}

onMounted(() => {
  void load()
})
</script>

<style scoped lang="scss">
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.filters {
  display: flex;
  gap: 10px;
}

.action-select {
  width: 180px;
}

.detail {
  font-family: Consolas, monospace;
  font-size: 12px;
  color: #606266;
  word-break: break-all;
}

.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
</style>
