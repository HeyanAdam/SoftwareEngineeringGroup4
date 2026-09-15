<script setup lang="ts">
/**
 * 通用 ECharts 容器。
 *  - 按需引入 echarts 模块 (core + Line/Bar/Pie + 常用组件)
 *  - ResizeObserver 自适应容器尺寸, 卸载时 dispose
 *  - 主题 (亮/暗) 变化时重建实例, 并重新调用 optionFactory 计算配置
 *  - optionFactory 每次都会拿到最新的响应式数据, 无需父组件深度监听
 */

import { onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { ElEmpty, ElSkeleton } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { LabelLayout, UniversalTransition } from 'echarts/features'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsCoreOption } from 'echarts/core'

import { useEchartsTheme } from '@/composables/useEchartsTheme'

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DatasetComponent,
  LabelLayout,
  UniversalTransition,
  CanvasRenderer,
])

const props = withDefaults(
  defineProps<{
    /** 生成 ECharts 配置的函数 (读取响应式数据, 主题变化时会重新执行) */
    optionFactory: () => EChartsCoreOption
    /**
     * 数据版本号: 数据变化后由父组件递增, 触发重新 setOption。
     * (函数类型的 prop 本身不参与响应式追踪, 因此显式传入版本号更可靠)
     */
    dataVersion?: number
    /** 图表高度, 支持任意 CSS 长度 */
    height?: string
    /** 加载态 (显示骨架遮罩) */
    loading?: boolean
    /** 数据为空时的提示文案 */
    emptyText?: string
    /** 是否在数据为空时展示占位 (默认 true) */
    showEmpty?: boolean
  }>(),
  {
    dataVersion: 0,
    height: '320px',
    loading: false,
    emptyText: '暂无数据',
    showEmpty: true,
  },
)

const emit = defineEmits<{
  (e: 'chart-click', params: unknown): void
}>()

const { themeName } = useEchartsTheme()

const containerRef = ref<HTMLDivElement | null>(null)
const chart = shallowRef<echarts.ECharts | null>(null)
const isEmpty = ref(false)
let observer: ResizeObserver | null = null

/** 是否为空数据 (按 series 数据量粗略判断) */
function checkEmpty(option: EChartsCoreOption): boolean {
  const series = (option as { series?: unknown }).series
  const list = Array.isArray(series) ? series : series ? [series] : []
  if (list.length === 0) return true
  return list.every((item) => {
    const data = (item as { data?: unknown[] }).data
    return Array.isArray(data) && data.length === 0
  })
}

/** 应用最新配置 (notMerge 避免残影) */
function applyOption(): void {
  if (!chart.value) return
  const option = props.optionFactory()
  isEmpty.value = checkEmpty(option)
  chart.value.setOption(option, { notMerge: true })
}

function createChart(): void {
  if (!containerRef.value) return
  chart.value?.dispose()
  chart.value = echarts.init(containerRef.value, themeName.value, { renderer: 'canvas' })
  chart.value.on('click', (params: unknown) => emit('chart-click', params))
  applyOption()
}

function handleWindowResize(): void {
  chart.value?.resize()
}

onMounted(() => {
  createChart()
  if (typeof ResizeObserver !== 'undefined' && containerRef.value) {
    observer = new ResizeObserver(() => chart.value?.resize())
    observer.observe(containerRef.value)
  } else {
    window.addEventListener('resize', handleWindowResize)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  window.removeEventListener('resize', handleWindowResize)
  chart.value?.dispose()
  chart.value = null
})

// 主题切换: theme 只能在 init 时指定, 必须重建实例
watch(themeName, () => createChart())

// 数据变化: 重新计算配置
watch(
  () => props.dataVersion,
  () => applyOption(),
)

defineExpose({
  /** 重新计算并应用配置 (父组件数据更新后可手动调用) */
  update: () => applyOption(),
  /** 手动重绘 (容器尺寸变化时使用) */
  resize: () => chart.value?.resize(),
  /** 获取底层实例 (导出图片等高级场景) */
  getInstance: () => chart.value,
})
</script>

<template>
  <div class="base-chart" :style="{ height }">
    <div ref="containerRef" class="base-chart__canvas"></div>

    <div v-if="showEmpty && isEmpty && !loading" class="base-chart__empty">
      <ElEmpty :description="emptyText" :image-size="72" />
    </div>

    <div v-if="loading" class="base-chart__loading">
      <ElSkeleton :rows="4" animated />
    </div>
  </div>
</template>

<style scoped lang="scss">
.base-chart {
  position: relative;
  width: 100%;

  &__canvas {
    width: 100%;
    height: 100%;
  }

  &__empty,
  &__loading {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: var(--app-bg-container);
  }
}
</style>
