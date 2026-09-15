/**
 * ECharts 主题: 根据当前亮/暗模式生成图表配色, 并注册到 echarts 实例。
 * 图表组件监听主题变化并重建实例 (ECharts 的 theme 只能在 init 时指定)。
 */

import { computed, watch, type ComputedRef } from 'vue'
import * as echarts from 'echarts/core'
import type { EChartsCoreOption } from 'echarts/core'

import { useAppStore } from '@/stores/app'

/** 主题名常量 (注册到 echarts 后作为 init 的第二参数) */
export const LIGHT_THEME = 'sg4-light'
export const DARK_THEME = 'sg4-dark'

/** 分类调色板 */
const PALETTE = [
  '#2563eb',
  '#0ea5e9',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#8b5cf6',
  '#14b8a6',
  '#f97316',
  '#6366f1',
  '#84cc16',
]

interface ThemeColors {
  textPrimary: string
  textSecondary: string
  axisLine: string
  splitLine: string
  tooltipBg: string
  tooltipText: string
  areaFrom: string
  areaTo: string
}

const LIGHT_COLORS: ThemeColors = {
  textPrimary: '#334155',
  textSecondary: '#64748b',
  axisLine: '#cbd5e1',
  splitLine: '#eef2f7',
  tooltipBg: 'rgba(255, 255, 255, 0.96)',
  tooltipText: '#1e293b',
  areaFrom: 'rgba(37, 99, 235, 0.28)',
  areaTo: 'rgba(37, 99, 235, 0.02)',
}

const DARK_COLORS: ThemeColors = {
  textPrimary: '#d1d5db',
  textSecondary: '#9ca3af',
  axisLine: '#3f4c63',
  splitLine: 'rgba(148, 163, 184, 0.16)',
  tooltipBg: 'rgba(27, 36, 55, 0.96)',
  tooltipText: '#e5e7eb',
  areaFrom: 'rgba(64, 158, 255, 0.32)',
  areaTo: 'rgba(64, 158, 255, 0.02)',
}

/** 生成 ECharts 主题对象 */
function buildTheme(colors: ThemeColors): Record<string, unknown> {
  return {
    color: PALETTE,
    backgroundColor: 'transparent',
    textStyle: { color: colors.textPrimary, fontFamily: 'inherit' },
    title: {
      textStyle: { color: colors.textPrimary, fontWeight: 600 },
      subtextStyle: { color: colors.textSecondary },
    },
    legend: {
      textStyle: { color: colors.textSecondary },
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 8,
    },
    tooltip: {
      backgroundColor: colors.tooltipBg,
      borderColor: colors.axisLine,
      borderWidth: 1,
      textStyle: { color: colors.tooltipText, fontSize: 12 },
      extraCssText: 'box-shadow: 0 6px 18px rgba(15,23,42,0.12); border-radius: 8px;',
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: colors.axisLine } },
      axisTick: { show: false },
      axisLabel: { color: colors.textSecondary },
      splitLine: { show: false },
    },
    valueAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: colors.textSecondary },
      splitLine: { lineStyle: { color: colors.splitLine, type: 'dashed' } },
    },
    line: {
      itemStyle: { borderWidth: 2 },
      lineStyle: { width: 2.5 },
      symbol: 'circle',
      symbolSize: 6,
      smooth: true,
    },
    bar: {
      itemStyle: { borderRadius: [6, 6, 0, 0] },
      barMaxWidth: 28,
    },
    pie: {
      itemStyle: { borderColor: colors.tooltipBg, borderWidth: 2 },
    },
  }
}

let registered = false

/** 注册主题 (幂等) */
function ensureThemesRegistered(): void {
  if (registered) return
  echarts.registerTheme(LIGHT_THEME, buildTheme(LIGHT_COLORS))
  echarts.registerTheme(DARK_THEME, buildTheme(DARK_COLORS))
  registered = true
}

/** 渐变面积色, 供折线图使用 */
export interface AreaGradientColors {
  from: string
  to: string
}

/** ECharts 线性渐变对象 (折线图 areaStyle.color) */
export interface LinearGradient {
  type: 'linear'
  x: number
  y: number
  x2: number
  y2: number
  colorStops: Array<{ offset: number; color: string }>
}

export interface UseEchartsThemeResult {
  /** 当前应使用的主题名 */
  themeName: ComputedRef<string>
  /** 折线图面积渐变配色 */
  areaGradient: ComputedRef<AreaGradientColors>
  /** 分类调色板 */
  palette: string[]
  /**
   * 主题/配色变化后触发 (BaseChart 用它在重建实例时重新计算 option)。
   * 直接调用会执行一次回调。
   */
  onThemeChange: (handler: (theme: string) => void) => void
}

export function useEchartsTheme(): UseEchartsThemeResult {
  const appStore = useAppStore()
  ensureThemesRegistered()

  const themeName = computed(() => (appStore.isDark ? DARK_THEME : LIGHT_THEME))
  const areaGradient = computed<AreaGradientColors>(() =>
    appStore.isDark
      ? { from: DARK_COLORS.areaFrom, to: DARK_COLORS.areaTo }
      : { from: LIGHT_COLORS.areaFrom, to: LIGHT_COLORS.areaTo },
  )

  /** 注册主题变化回调 (立即执行一次) */
  function onThemeChange(handler: (theme: string) => void): void {
    watch(themeName, (value) => handler(value), { immediate: true })
  }

  return { themeName, areaGradient, palette: PALETTE, onThemeChange }
}

/** 生成 ECharts 线性渐变面积色对象 */
export function linearAreaStyle(colors: AreaGradientColors): { color: LinearGradient } {
  return {
    color: {
      type: 'linear',
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: colors.from },
        { offset: 1, color: colors.to },
      ],
    },
  }
}

export type { EChartsCoreOption }
