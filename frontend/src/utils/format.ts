/**
 * 格式化工具函数
 */

/**
 * 格式化文件大小
 * @param bytes 字节数
 * @returns 格式化后的字符串
 */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

/**
 * 格式化日期时间
 * @param dateStr 日期字符串
 * @returns 格式化后的日期时间字符串
 */
export function formatDateTime(dateStr: string): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/**
 * 格式化百分比
 * @param value 小数值 (0-1)
 * @param decimals 小数位数
 * @returns 格式化后的百分比字符串
 */
export function formatPercent(value: number, decimals: number = 1): string {
  return (value * 100).toFixed(decimals) + '%'
}

/**
 * 格式化置信度
 * @param confidence 置信度 (0-1)
 * @returns 格式化后的字符串
 */
export function formatConfidence(confidence: number): string {
  return (confidence * 100).toFixed(1) + '%'
}
