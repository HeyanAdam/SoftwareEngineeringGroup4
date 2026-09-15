<script setup lang="ts">
/** 数据仪表盘: 指标卡 + 4 张 ECharts 图表 (折线/柱状/饼图/横向柱状) */

import { computed, markRaw, onMounted, ref, type Component } from 'vue'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElIcon,
  ElSkeleton,
  ElTag,
  ElTooltip,
} from 'element-plus'
import {
  ChatDotRound,
  DataLine,
  Document,
  Refresh,
  TrendCharts,
  User,
} from '@element-plus/icons-vue'
import type { EChartsCoreOption } from 'echarts/core'

import BaseChart from '@/components/charts/BaseChart.vue'
import PageContainer from '@/components/common/PageContainer.vue'
import { getOverview } from '@/api/dashboard'
import { linearAreaStyle, useEchartsTheme } from '@/composables/useEchartsTheme'
import { formatDelta, formatDateTime, formatNumber } from '@/utils/format'
import type { DashboardOverview, DashboardStat } from '@/types/dashboard'
import type { NormalizedApiError } from '@/types/common'

const appTitle = import.meta.env.VITE_APP_TITLE ?? 'SG4 管理后台'
const TREND_DAYS = 30

const loading = ref(false)
const errorMessage = ref('')
const overview = ref<DashboardOverview | null>(null)
/** 数据版本号: 每次加载后递增, 通知图表重新 setOption */
const dataVersion = ref(0)

const { areaGradient, palette } = useEchartsTheme()

/** 指标卡图标映射 (按后端返回的 key) */
const STAT_ICONS: Record<string, Component> = {
  total_users: markRaw(User),
  active_users: markRaw(TrendCharts),
  files: markRaw(Document),
  uploads: markRaw(Document),
  messages: markRaw(ChatDotRound),
}

const stats = computed<DashboardStat[]>(() => overview.value?.stats ?? [])
const chartHeight = '320px'

function iconOf(stat: DashboardStat): Component {
  return STAT_ICONS[stat.key] ?? markRaw(DataLine)
}

async function loadData(refresh = false): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    overview.value = await getOverview({ days: TREND_DAYS, refresh })
    dataVersion.value += 1
  } catch (error) {
    errorMessage.value = (error as NormalizedApiError)?.message ?? '仪表盘数据加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadData(false)
})

/* ------------------------------- 图表配置 ------------------------------- */

/** 1. 趋势折线图 */
function trendOption(): EChartsCoreOption {
  const points = overview.value?.trend ?? []
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 12, right: 20, top: 24, bottom: 8, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: points.map((item) => item.label) },
    yAxis: { type: 'value' },
    series: [
      {
        name: '活跃用户',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: points.map((item) => item.value),
        areaStyle: linearAreaStyle(areaGradient.value),
      },
    ],
  }
}

/** 2. 分类柱状图 */
function categoryOption(): EChartsCoreOption {
  const points = overview.value?.categories ?? []
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 20, top: 24, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: points.map((item) => item.label),
      axisLabel: { interval: 0, rotate: points.length > 5 ? 20 : 0 },
    },
    yAxis: { type: 'value' },
    series: [
      {
        name: '数量',
        type: 'bar',
        data: points.map((item) => item.value),
        itemStyle: { color: palette[0], borderRadius: [6, 6, 0, 0] },
      },
    ],
  }
}

/** 3. 角色分布环形图 */
function roleOption(): EChartsCoreOption {
  const points = overview.value?.role_distribution ?? []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        name: '角色分布',
        type: 'pie',
        radius: ['46%', '68%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: 'transparent', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{d}%' },
        data: points.map((item) => ({ name: item.label, value: item.value })),
      },
    ],
  }
}

/** 4. 分类占比横向柱状图 (补充维度: 直观比较各分类体量) */
function rankingOption(): EChartsCoreOption {
  const points = [...(overview.value?.categories ?? [])].sort((a, b) => a.value - b.value)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 40, top: 20, bottom: 8, containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: points.map((item) => item.label) },
    series: [
      {
        name: '占比排行',
        type: 'bar',
        data: points.map((item) => item.value),
        label: { show: true, position: 'right' },
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: palette[1] },
              { offset: 1, color: palette[0] },
            ],
          },
        },
      },
    ],
  }
}
</script>

<template>
  <PageContainer title="数据仪表盘" :description="`${appTitle} 平台运行总览`">
    <template #actions>
      <ElTooltip content="跳过缓存重新统计" placement="top">
        <ElButton :icon="Refresh" :loading="loading" @click="loadData(true)">刷新数据</ElButton>
      </ElTooltip>
    </template>

    <ElAlert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="mb-16"
    />

    <div class="dashboard">
      <section class="dashboard__stats">
        <ElCard v-for="stat in stats" :key="stat.key" shadow="hover" class="dashboard__stat-card">
          <div class="dashboard__stat-body">
            <div class="dashboard__stat-icon">
              <ElIcon :size="22"><component :is="iconOf(stat)" /></ElIcon>
            </div>
            <div class="dashboard__stat-meta">
              <span class="dashboard__stat-label">{{ stat.label }}</span>
              <span class="dashboard__stat-value">
                {{ formatNumber(stat.value) }}
                <small v-if="stat.unit">{{ stat.unit }}</small>
              </span>
              <span
                v-if="typeof stat.delta === 'number'"
                class="dashboard__stat-delta"
                :class="stat.delta >= 0 ? 'is-up' : 'is-down'"
              >
                {{ formatDelta(stat.delta) }} 环比
              </span>
            </div>
          </div>
        </ElCard>

        <ElSkeleton
          v-if="loading && stats.length === 0"
          :rows="1"
          animated
          class="dashboard__stat-skeleton"
        />
      </section>

      <section class="dashboard__grid">
        <ElCard shadow="never" class="dashboard__chart-card">
          <template #header>
            <div class="dashboard__chart-header">
              <span>近 {{ TREND_DAYS }} 天活跃趋势</span>
              <ElTag size="small" effect="light" type="info">{{ overview?.trend.length ?? 0 }} 个数据点</ElTag>
            </div>
          </template>
          <BaseChart
            :option-factory="trendOption"
            :data-version="dataVersion"
            :height="chartHeight"
            :loading="loading"
            empty-text="暂无趋势数据"
          />
        </ElCard>

        <ElCard shadow="never" class="dashboard__chart-card">
          <template #header>
            <div class="dashboard__chart-header">
              <span>角色分布</span>
              <ElTag size="small" effect="light" type="info">
                {{ overview?.role_distribution.length ?? 0 }} 个角色
              </ElTag>
            </div>
          </template>
          <BaseChart
            :option-factory="roleOption"
            :data-version="dataVersion"
            :height="chartHeight"
            :loading="loading"
            empty-text="暂无角色数据"
          />
        </ElCard>

        <ElCard shadow="never" class="dashboard__chart-card">
          <template #header>
            <div class="dashboard__chart-header">
              <span>分类数量对比</span>
              <ElTag size="small" effect="light" type="info">
                {{ overview?.categories.length ?? 0 }} 个分类
              </ElTag>
            </div>
          </template>
          <BaseChart
            :option-factory="categoryOption"
            :data-version="dataVersion"
            :height="chartHeight"
            :loading="loading"
            empty-text="暂无分类数据"
          />
        </ElCard>

        <ElCard shadow="never" class="dashboard__chart-card">
          <template #header>
            <div class="dashboard__chart-header">
              <span>分类体量排行</span>
              <span class="text-muted">横向对比</span>
            </div>
          </template>
          <BaseChart
            :option-factory="rankingOption"
            :data-version="dataVersion"
            :height="chartHeight"
            :loading="loading"
            empty-text="暂无排行数据"
          />
        </ElCard>
      </section>

      <footer class="dashboard__footer">
        数据生成时间: {{ formatDateTime(overview?.generated_at) }}
      </footer>
    </div>
  </PageContainer>
</template>

<style scoped lang="scss">
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;

  &__stats {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 14px;
  }

  &__stat-card {
    border-radius: var(--app-radius-md);
  }

  &__stat-body {
    display: flex;
    gap: 14px;
    align-items: center;
  }

  &__stat-icon {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
    width: 46px;
    height: 46px;
    color: var(--app-color-primary);
    background-color: rgb(37 99 235 / 10%);
    border-radius: 12px;
  }

  &__stat-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  &__stat-label {
    font-size: 12px;
    color: var(--app-text-secondary);
  }

  &__stat-value {
    font-size: 22px;
    font-weight: 700;
    color: var(--app-text-primary);

    small {
      margin-left: 2px;
      font-size: 12px;
      font-weight: 500;
      color: var(--app-text-placeholder);
    }
  }

  &__stat-delta {
    font-size: 12px;

    &.is-up {
      color: var(--app-color-success);
    }

    &.is-down {
      color: var(--app-color-danger);
    }
  }

  &__stat-skeleton {
    grid-column: span 2;
  }

  &__grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
    gap: 16px;
  }

  &__chart-card {
    border-radius: var(--app-radius-md);
  }

  &__chart-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 14px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  &__footer {
    padding-top: 4px;
    font-size: 12px;
    color: var(--app-text-placeholder);
    text-align: right;
  }
}

@media (width <= 760px) {
  .dashboard__grid {
    grid-template-columns: 1fr;
  }
}
</style>
