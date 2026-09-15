/** 展示层格式化工具 (纯函数, 便于单元测试) */

const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'] as const

function pad(value: number): string {
  return value < 10 ? `0${value}` : String(value)
}

/** 解析后端时间字符串 / 时间戳 / Date */
function toDate(value: string | number | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === '') return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/**
 * 格式化为 `YYYY-MM-DD HH:mm:ss`
 * @param value ISO 字符串 / 时间戳 / Date
 * @param fallback 无效值时的占位符
 */
export function formatDateTime(
  value: string | number | Date | null | undefined,
  fallback = '-',
): string {
  const date = toDate(value)
  if (!date) return fallback
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ` +
    `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}

/** 格式化为 `YYYY-MM-DD` */
export function formatDate(
  value: string | number | Date | null | undefined,
  fallback = '-',
): string {
  const date = toDate(value)
  if (!date) return fallback
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 相对时间 (刚刚 / N 分钟前 / N 小时前 / N 天前 / 具体日期) */
export function formatRelativeTime(
  value: string | number | Date | null | undefined,
  fallback = '-',
): string {
  const date = toDate(value)
  if (!date) return fallback
  const diff = Date.now() - date.getTime()
  if (diff < 0) return formatDateTime(date)
  const minute = 60_000
  const hour = 60 * minute
  const day = 24 * hour

  if (diff < minute) return '刚刚'
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`
  if (diff < 30 * day) return `${Math.floor(diff / day)} 天前`
  return formatDate(date)
}

/**
 * 字节数 -> 人类可读体积 (1024 进制, 最多一位小数)
 * formatBytes(0) === '0 B'
 */
export function formatBytes(bytes: number | null | undefined, decimals = 1): string {
  if (bytes === null || bytes === undefined || !Number.isFinite(bytes)) return '-'
  if (bytes <= 0) return '0 B'
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), BYTE_UNITS.length - 1)
  const value = bytes / 1024 ** exponent
  const unit = BYTE_UNITS[exponent] ?? 'B'
  if (exponent === 0) return `${Math.round(value)} ${unit}`
  return `${value.toFixed(decimals)} ${unit}`
}

/**
 * 数字千分位格式化
 * formatNumber(1234567) === '1,234,567'
 */
export function formatNumber(value: number | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-'
  return value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

/** 百分比格式化, 入参为 0-1 的比率 */
export function formatPercent(ratio: number | null | undefined, decimals = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '-'
  return `${(ratio * 100).toFixed(decimals)}%`
}

/** 带符号的增量 (指标卡 delta), 入参为 0-1 的比率 */
export function formatDelta(delta: number | null | undefined, decimals = 1): string {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return '-'
  const sign = delta > 0 ? '+' : ''
  return `${sign}${(delta * 100).toFixed(decimals)}%`
}

/** 截断过长文本 */
export function truncate(text: string | null | undefined, max = 36, suffix = '…'): string {
  if (!text) return ''
  return text.length <= max ? text : `${text.slice(0, max)}${suffix}`
}

/** 用户名首字母 / 中文首字, 用于头像占位 */
export function initialsOf(name: string | null | undefined): string {
  const value = (name ?? '').trim()
  if (!value) return '?'
  return value.slice(0, 1).toUpperCase()
}
