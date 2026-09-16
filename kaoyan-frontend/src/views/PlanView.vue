<template>
  <div class="plan-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span class="card-title">我的学习计划</span>
          <el-button type="primary" @click="openCreateDialog">
            <el-icon><Plus /></el-icon>
            新建计划
          </el-button>
        </div>
      </template>

      <el-table
        :loading="loading"
        :data="plans"
        row-key="id"
        :expand-row-keys="expandedRowKeys"
        empty-text="还没有学习计划，点击右上角「新建计划」开始"
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="task-panel">
              <div v-if="taskLoadingId === row.id" class="task-loading">任务加载中…</div>
              <el-table
                v-else
                :data="taskMap[row.id] ?? []"
                size="small"
                empty-text="该计划暂无任务"
              >
                <el-table-column prop="day_index" label="第几天" width="80" />
                <el-table-column prop="title" label="任务内容" min-width="200" />
                <el-table-column prop="scheduled_date" label="计划日期" width="130" />
                <el-table-column label="状态" width="110">
                  <template #default="taskScope">
                    <el-switch
                      :model-value="taskScope.row.status === 'done'"
                      active-text="已完成"
                      inactive-text="未完成"
                      inline-prompt
                      @change="handleTaskStatusChange(taskScope.row)"
                    />
                  </template>
                </el-table-column>
                <el-table-column prop="note" label="备注" min-width="140" />
              </el-table>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="计划标题" min-width="160" show-overflow-tooltip />
        <el-table-column prop="subject" label="科目" width="110" />
        <el-table-column label="起止日期" width="220">
          <template #default="{ row }">{{ row.start_date }} ~ {{ row.end_date }}</template>
        </el-table-column>
        <el-table-column label="每日时长" width="100">
          <template #default="{ row }">{{ row.daily_minutes }} 分钟</template>
        </el-table-column>
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="clampPercent(row.progress)" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="light">
              {{ statusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click.stop="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建计划弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建学习计划" width="520px" @open="handleDialogOpen">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="计划标题" prop="title">
          <el-input v-model="form.title" placeholder="例如：考研数学基础强化" clearable />
        </el-form-item>
        <el-form-item label="科目" prop="subject">
          <el-select v-model="form.subject" placeholder="请选择科目" class="full-width">
            <el-option v-for="item in subjects" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="起止日期" prop="dateRange">
          <el-date-picker
            v-model="form.dateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            class="full-width"
          />
        </el-form-item>
        <el-form-item label="每日时长" prop="daily_minutes">
          <el-input-number
            v-model="form.daily_minutes"
            :min="10"
            :max="720"
            :step="10"
            @change="handleDailyMinutesChange"
          />
          <span class="unit-tip">分钟</span>
        </el-form-item>
        <el-form-item label="备注" prop="note">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="选填，例如复习重点、参考书目"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

import { createPlan, deletePlan, getPlan, listPlans, updateTask } from '@/api/plan'
import type { CreatePlanPayload, PlanForm, PlanTask, StudyPlan } from '@/types/plan'

/** 新建计划表单：在 API 载荷基础上把 start_date/end_date 换成日期区间组件需要的 dateRange */
interface PlanFormModel extends Omit<PlanForm, 'start_date' | 'end_date'> {
  dateRange: [string, string] | null
}

const subjects = ['数学', '英语', '政治', '专业课', '其他']

const plans = ref<StudyPlan[]>([])
const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()

/** 展开行的 key（受控的展开状态） */
const expandedRowKeys = ref<number[]>([])
/** 计划 id -> 任务列表（展开时才按需加载，未加载时为 undefined） */
const taskMap = reactive<Record<number, PlanTask[] | undefined>>({})
const taskLoadingId = ref<number | null>(null)

const form = reactive<PlanFormModel>({
  title: '',
  subject: '',
  dateRange: null,
  daily_minutes: 60,
  note: '',
})

const rules: FormRules<PlanFormModel> = {
  title: [{ required: true, message: '请输入计划标题', trigger: 'blur' }],
  subject: [{ required: true, message: '请选择科目', trigger: 'change' }],
  dateRange: [{ required: true, message: '请选择起止日期', trigger: 'change' }],
}

/** 状态 -> 中文文案 */
function statusText(status: string): string {
  if (status === 'completed') return '已完成'
  if (status === 'active') return '进行中'
  if (status === 'pending') return '未开始'
  return status
}

/** 状态 -> el-tag 类型 */
function statusTagType(status: string): 'success' | 'primary' | 'warning' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'active') return 'primary'
  if (status === 'pending') return 'info'
  return 'warning'
}

/** 进度可能超过 100 或为负，做一次收敛 */
function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(Math.max(Math.round(value), 0), 100)
}

function openCreateDialog(): void {
  dialogVisible.value = true
}

/** 弹窗打开时重置表单，避免上一次的输入与校验残留 */
function handleDialogOpen(): void {
  form.title = ''
  form.subject = ''
  form.dateRange = null
  form.daily_minutes = 60
  form.note = ''
  formRef.value?.clearValidate()
}

/** el-input-number 清空时会传 null，这里兜底回默认值 */
function handleDailyMinutesChange(value: number | undefined): void {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    form.daily_minutes = 60
  }
}

async function loadPlans(): Promise<void> {
  loading.value = true
  try {
    plans.value = await listPlans()
    // 计划可能已被删除，清掉不再存在的展开态
    const validIds = new Set(plans.value.map((item) => item.id))
    expandedRowKeys.value = expandedRowKeys.value.filter((id) => validIds.has(id))
  } catch {
    ElMessage.warning('计划列表获取失败')
  } finally {
    loading.value = false
  }
}

/** 加载某个计划的任务列表 */
async function loadTasks(planId: number): Promise<void> {
  taskLoadingId.value = planId
  try {
    const detail = await getPlan(planId)
    taskMap[planId] = detail.tasks
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    taskLoadingId.value = null
  }
}

/** 展开计划详情时按需拉取任务（已加载过就不重复请求） */
function handleExpandChange(row: StudyPlan, expandedRows: StudyPlan[]): void {
  const expanded = expandedRows.some((item) => item.id === row.id)
  if (expanded) {
    if (!expandedRowKeys.value.includes(row.id)) {
      expandedRowKeys.value = [...expandedRowKeys.value, row.id]
    }
    if (!taskMap[row.id]) {
      void loadTasks(row.id)
    }
  } else {
    expandedRowKeys.value = expandedRowKeys.value.filter((id) => id !== row.id)
  }
}

/** 切换任务完成状态：成功后本地刷新该计划的进度统计 */
async function handleTaskStatusChange(task: PlanTask): Promise<void> {
  const previous = task.status
  const nextStatus = previous === 'done' ? 'pending' : 'done'
  task.status = nextStatus
  try {
    const updated = await updateTask(task.id, { status: nextStatus })
    task.status = updated.status
    updatePlanProgress(task.plan_id)
    ElMessage.success(nextStatus === 'done' ? '任务已完成' : '已标记为未完成')
  } catch {
    // 失败回滚开关状态
    task.status = previous
  }
}

/** 根据任务完成情况本地重算计划的进度，避免整表重新拉取 */
function updatePlanProgress(planId: number): void {
  const tasks = taskMap[planId]
  const plan = plans.value.find((item) => item.id === planId)
  if (!tasks || !plan) return
  const done = tasks.filter((item) => item.status === 'done').length
  plan.task_done = done
  plan.task_total = tasks.length
  plan.progress = tasks.length === 0 ? 0 : Math.round((done / tasks.length) * 100)
  if (tasks.length > 0) {
    plan.status = done === tasks.length ? 'completed' : 'active'
  }
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  const range = form.dateRange
  if (!valid || !range) return

  const payload: CreatePlanPayload = {
    title: form.title.trim(),
    subject: form.subject,
    start_date: range[0],
    end_date: range[1],
    daily_minutes: form.daily_minutes,
  }
  const note = form.note?.trim()
  if (note) {
    payload.note = note
  }

  submitting.value = true
  try {
    await createPlan(payload)
    ElMessage.success('计划创建成功')
    dialogVisible.value = false
    await loadPlans()
  } catch {
    // 错误提示已由拦截器统一处理
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: StudyPlan): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除计划「${row.title}」及其所有任务吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    // 用户取消
    return
  }

  try {
    await deletePlan(row.id)
    ElMessage.success('已删除')
    delete taskMap[row.id]
    expandedRowKeys.value = expandedRowKeys.value.filter((id) => id !== row.id)
    await loadPlans()
  } catch {
    // 错误提示已由拦截器统一处理
  }
}

onMounted(() => {
  void loadPlans()
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

.full-width {
  width: 100%;
}

.unit-tip {
  margin-left: 8px;
  font-size: 13px;
  color: #909399;
}

.task-panel {
  padding: 8px 16px 12px 48px;
}

.task-loading {
  padding: 12px 0;
  font-size: 13px;
  color: #909399;
}
</style>
