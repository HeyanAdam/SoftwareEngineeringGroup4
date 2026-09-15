/** 格式化工具单元测试 (纯函数, 确定性) */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  formatBytes,
  formatDate,
  formatDateTime,
  formatDelta,
  formatNumber,
  formatPercent,
  formatRelativeTime,
  initialsOf,
  truncate,
} from '@/utils/format'

describe('formatBytes', () => {
  it('按 1024 进制换算并保留单位', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(5 * 1024 ** 3)).toBe('5.0 GB')
  })

  it('非法输入返回占位符', () => {
    expect(formatBytes(null)).toBe('-')
    expect(formatBytes(undefined)).toBe('-')
    expect(formatBytes(Number.NaN)).toBe('-')
    expect(formatBytes(-1)).toBe('0 B')
  })

  it('支持自定义小数位', () => {
    expect(formatBytes(1536, 2)).toBe('1.50 KB')
  })
})

describe('formatNumber', () => {
  it('使用千分位', () => {
    expect(formatNumber(0)).toBe('0')
    expect(formatNumber(1234)).toBe('1,234')
    expect(formatNumber(1234567)).toBe('1,234,567')
  })

  it('支持小数位与非法输入', () => {
    expect(formatNumber(1234.567, 2)).toBe('1,234.57')
    expect(formatNumber(null)).toBe('-')
    expect(formatNumber(Number.POSITIVE_INFINITY)).toBe('-')
  })
})

describe('formatDateTime / formatDate', () => {
  const date = new Date(2024, 4, 6, 8, 9, 10)

  it('输出本地时间字符串', () => {
    expect(formatDateTime(date)).toBe('2024-05-06 08:09:10')
    expect(formatDate(date)).toBe('2024-05-06')
  })

  it('接受 ISO 字符串', () => {
    expect(formatDateTime(date.toISOString())).toBe('2024-05-06 08:09:10')
  })

  it('非法输入返回占位符', () => {
    expect(formatDateTime(null)).toBe('-')
    expect(formatDateTime('not-a-date')).toBe('-')
    expect(formatDateTime('', '无')).toBe('无')
  })
})

describe('formatRelativeTime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2024, 4, 6, 12, 0, 0))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('按时间差返回中文描述', () => {
    const now = Date.now()
    expect(formatRelativeTime(now - 10_000)).toBe('刚刚')
    expect(formatRelativeTime(now - 5 * 60_000)).toBe('5 分钟前')
    expect(formatRelativeTime(now - 3 * 3_600_000)).toBe('3 小时前')
    expect(formatRelativeTime(now - 2 * 86_400_000)).toBe('2 天前')
  })

  it('超出 30 天回退为日期', () => {
    const old = new Date(2024, 0, 1).getTime()
    expect(formatRelativeTime(old)).toBe('2024-01-01')
  })
})

describe('formatPercent / formatDelta', () => {
  it('百分比与带符号增量', () => {
    expect(formatPercent(0.1234)).toBe('12.3%')
    expect(formatDelta(0.08)).toBe('+8.0%')
    expect(formatDelta(-0.052)).toBe('-5.2%')
    expect(formatDelta(0)).toBe('0.0%')
    expect(formatPercent(null)).toBe('-')
    expect(formatDelta(undefined)).toBe('-')
  })
})

describe('truncate / initialsOf', () => {
  it('截断超长文本', () => {
    expect(truncate('abcdef', 4)).toBe('abcd…')
    expect(truncate('abc', 4)).toBe('abc')
    expect(truncate(null)).toBe('')
  })

  it('取首字符作为头像文案', () => {
    expect(initialsOf('alice')).toBe('A')
    expect(initialsOf('张三')).toBe('张')
    expect(initialsOf('   ')).toBe('?')
    expect(initialsOf(null)).toBe('?')
  })
})
