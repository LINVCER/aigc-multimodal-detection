/**
 * 颜色工具函数 - 统一置信度和风险等级的颜色映射
 */

/**
 * 根据置信度返回颜色
 * @param score 置信度 (0-1)
 * @returns 颜色值
 */
export function confidenceColor(score: number): string {
  if (score >= 0.7) return '#dc2626' // 红色 - 高风险
  if (score >= 0.3) return '#f59e0b' // 橙色 - 中风险
  return '#10b981' // 绿色 - 低风险
}

/**
 * 根据置信度返回背景色（带透明度）
 * @param score 置信度 (0-1)
 * @returns 背景颜色值
 */
export function confidenceBgColor(score: number): string {
  if (score >= 0.7) return 'rgba(220, 38, 38, 0.1)' // 红色背景
  if (score >= 0.3) return 'rgba(245, 158, 11, 0.1)' // 橙色背景
  return 'rgba(16, 185, 129, 0.1)' // 绿色背景
}

/**
 * 根据风险等级返回Element Plus标签类型
 * @param level 风险等级
 * @returns Element Plus类型
 */
export function riskTagType(level: string): string {
  const mapping: Record<string, string> = {
    low: 'success',
    medium: 'warning',
    high: 'danger',
  }
  return mapping[level] || 'info'
}

/**
 * 根据风险等级返回中文文本
 * @param level 风险等级
 * @returns 中文文本
 */
export function riskText(level: string): string {
  const mapping: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
  }
  return mapping[level] || '未知'
}

/**
 * 根据风险等级返回颜色
 * @param level 风险等级
 * @returns 颜色值
 */
export function riskColor(level: string): string {
  const mapping: Record<string, string> = {
    low: '#10b981',
    medium: '#f59e0b',
    high: '#dc2626',
  }
  return mapping[level] || '#6b7280'
}
