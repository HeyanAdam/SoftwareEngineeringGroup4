<template>
  <div class="home">
    <!-- 欢迎区 -->
    <el-card class="welcome-card" shadow="never">
      <div class="welcome">
        <div>
          <h2 class="welcome-title">{{ greeting }}，{{ authStore.displayName }}！</h2>
          <p class="welcome-desc">
            这里是你的考研备考看板，可以随时向 AI 提问、管理学习计划并跟踪任务完成情况。
          </p>
        </div>
        <div class="welcome-actions">
          <el-button type="primary" @click="goChat">
            <el-icon><ChatDotRound /></el-icon>
            去问 AI
          </el-button>
          <el-button plain @click="goPlans">
            <el-icon><Calendar /></el-icon>
            学习计划
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col v-for="card in statCards" :key="card.key" :xs="24" :sm="12" :md="6">
        <el-card class="stat-card" shadow="hover">
          <div class="stat-body">
            <el-icon :size="28" :color="card.color">
              <component :is="card.icon" />
            </el-icon>
            <div class="stat-text">
              <div class="stat-label">{{ card.label }}</div>
              <div class="stat-value">
                {{ card.value }}
                <span class="stat-unit">{{ card.unit }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表 -->
    <el-card class="chart-card" shadow="never">
      <template #header>
        <div class="chart-header">
          <span>各计划任务完成情况</span>
          <el-button link type="primary" :loading="loading" @click="loadAll">
            <el-icon><Search /></el-icon>
            刷新
          </el-button>
        </div>
      </template>
      <div ref="chartRef" class="chart"></div>
      <el-empty v-if="!loading && plans.length === 0" description="还没有学习计划，先去创建一个吧" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Calendar,
  ChatDotRound,
  DataAnalysis,
  Document,
  Search,
  UserFilled,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption, EChartsType } from 'echarts/core'
import type { Component } from 'vue'

import { getStats, listPlans } from '@/api/plan'
import { useAuthStore } from '@/stores/auth'
import type { PlanStats, StudyPlan } from '@/types/plan'

// ECharts 按需注册：只用柱状图 + 网格 + 提示框
echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const stats = ref<PlanStats>({
  plan_total: 0,
  plan_active: 0,
  task_total: 0,
  task_done: 0,
  completion_rate: 0,
})
const plans = ref<StudyPlan[]>([])
const chartRef = ref<HTMLDivElement>()
// 图表实例不放进 ref：它不需要响应式，避免被 Proxy 包装影响 ECharts 内部逻辑
let chart: EChartsType | null = null
let resizeObserver: ResizeObserver | null = null

/** 按当前时间给出问候语 */
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

/** 统计卡片结构 */
interface StatCard {
  key: string
  label: string
  value: number
  unit: string
  icon: Component
  color: string
}

/** 4 个统计卡片（图标显式标注为 Component，避免 <component :is> 的联合类型报错） */
const statCards = computed<StatCard[]>(() => [
  {
    key: 'plan_total',
    label: '计划总数',
    value: stats.value.plan_total,
    unit: '个',
    icon: Calendar,
    color: '#409eff',
  },
  {
    key: 'plan_active',
    label: '进行中计划',
    value: stats.value.plan_active,
    unit: '个',
    icon: DataAnalysis,
    color: '#67c23a',
  },
  {
    key: 'task_total',
    label: '任务总数',
    value: stats.value.task_total,
    unit: '项',
    icon: Document,
    color: '#e6a23c',
  },
  {
    key: 'completion_rate',
    label: '任务完成率',
    value: stats.value.completion_rate,
    unit: '%',
    icon: UserFilled,
    color: '#f56c6c',
  },
])

/** 构造柱状图配置：对比每个计划的任务完成数与剩余数 */
function buildChartOption(data: StudyPlan[]): EChartsCoreOption {
  const names = data.map((plan) => plan.title)
  const doneCounts = data.map((plan) => plan.task_done)
  const pendingCounts = data.map((plan) => Math.max(plan.task_total - plan.task_done, 0))

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: ['已完成', '未完成'],
      top: 0,
    },
    grid: {
      left: 12,
      right: 20,
      bottom: 8,
      top: 44,
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { interval: 0, rotate: names.length > 5 ? 20 : 0 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
    },
    series: [
      {
        name: '已完成',
        type: 'bar',
        stack: 'task',
        barMaxWidth: 36,
        itemStyle: { color: '#409eff', borderRadius: [0, 0, 0, 0] },
        data: doneCounts,
      },
      {
        name: '未完成',
        type: 'bar',
        stack: 'task',
        barMaxWidth: 36,
        itemStyle: { color: '#e4e7ed', borderRadius: [4, 4, 0, 0] },
        data: pendingCounts,
      },
    ],
  }
}

/** 渲染图表（没有数据时清空画布） */
function renderChart(): void {
  if (!chart) return
  if (plans.value.length === 0) {
    chart.clear()
    return
  }
  chart.setOption(buildChartOption(plans.value), true)
}

/** 初始化图表实例与自适应监听 */
function initChart(): void {
  const el = chartRef.value
  if (!el) return
  chart = echarts.init(el)
  renderChart()
  // 侧边栏折叠 / 窗口缩放时容器宽度会变化，用 ResizeObserver 自适应
  resizeObserver = new ResizeObserver(() => {
    chart?.resize()
  })
  resizeObserver.observe(el)
}

/**
 * 加载统计数据与计划列表。
 * 统计接口失败时优雅降级为 0（拦截器已弹出提示），计划接口失败也不阻塞页面。
 */
async function loadAll(): Promise<void> {
  loading.value = true
  const [statsResult, plansResult] = await Promise.allSettled([getStats(), listPlans()])

  if (statsResult.status === 'fulfilled') {
    stats.value = statsResult.value
  } else {
    stats.value = { plan_total: 0, plan_active: 0, task_total: 0, task_done: 0, completion_rate: 0 }
    ElMessage.warning('统计数据获取失败，已显示默认值')
  }

  if (plansResult.status === 'fulfilled') {
    plans.value = plansResult.value
  } else {
    plans.value = []
    ElMessage.warning('计划列表获取失败')
  }

  renderChart()
  loading.value = false
}

function goChat(): void {
  void router.push('/chat')
}

function goPlans(): void {
  void router.push('/plans')
}

onMounted(() => {
  initChart()
  void loadAll()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.dispose()
  chart = null
})
</script>

<style scoped lang="scss">
.welcome-card {
  margin-bottom: 20px;
}

.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.welcome-title {
  margin: 0 0 6px;
  font-size: 20px;
}

.welcome-desc {
  margin: 0;
  font-size: 13px;
  color: #909399;
}

.stat-row {
  margin-bottom: 4px;
}

.stat-card {
  margin-bottom: 20px;
}

.stat-body {
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-text {
  flex: 1;
  min-width: 0;
}

.stat-label {
  font-size: 13px;
  color: #909399;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  line-height: 1.3;
}

.stat-unit {
  font-size: 13px;
  font-weight: 400;
  color: #909399;
  margin-left: 2px;
}

.chart-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart {
  width: 100%;
  height: 340px;
}
</style>
