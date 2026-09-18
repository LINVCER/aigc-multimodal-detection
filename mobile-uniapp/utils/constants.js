// 全局常量：状态、学位类型、来源标签、阈值判定
// 与后端 detect_task.status / paper.degree_type / detect_paragraph_result.source_label 对齐

export const STATUS_MAP = {
  PENDING: { text: '排队中', color: '#9ca3af', bg: '#f3f4f6' },
  RUNNING: { text: '检测中', color: '#f59e0b', bg: '#fef3c7' },
  DONE:    { text: '已完成', color: '#10b981', bg: '#d1fae5' },
  FAILED:  { text: '失败',   color: '#ef4444', bg: '#fee2e2' },
}

export const DEGREE_MAP = {
  BACHELOR: { label: '本科', threshold: 20 },
  MASTER:   { label: '硕士', threshold: 15 },
  PHD:      { label: '博士', threshold: 10 },
}

export const SOURCE_MAP = {
  human:    { label: '人类',       color: '#10b981' },
  gpt:      { label: 'GPT',        color: '#8b5cf6' },
  claude:   { label: 'Claude',     color: '#ec4899' },
  qwen:     { label: '通义千问',    color: '#f59e0b' },
  deepseek: { label: 'DeepSeek',   color: '#3b82f6' },
  glm:      { label: '智谱GLM',    color: '#06b6d4' },
  kimi:     { label: 'Kimi',       color: '#a855f7' },
  ernie:    { label: '文心',       color: '#ef4444' },
  other:    { label: '其他',       color: '#6b7280' },
}

export const STATUS_FILTER_OPTIONS = [
  { key: 'ALL',     text: '全部' },
  { key: 'RUNNING', text: '进行中' },
  { key: 'DONE',    text: '已完成' },
  { key: 'FAILED',  text: '失败' },
]

/**
 * AI 率相对红线的颜色分档
 * @param {number} rate 0-100
 * @param {number} threshold 红线
 * @returns 颜色 hex
 */
export function aiRateColor(rate, threshold) {
  if (rate == null) return '#9ca3af'
  if (rate <= threshold) return '#10b981'
  if (rate <= threshold * 1.5) return '#f59e0b'
  return '#ef4444'
}

/**
 * 段落 AI 概率 → 高中低风险
 */
export function paragraphRisk(prob) {
  if (prob >= 0.7) return { level: 'high', color: '#ef4444', bg: '#fee2e2' }
  if (prob >= 0.4) return { level: 'medium', color: '#f59e0b', bg: '#fef3c7' }
  return { level: 'low', color: '#10b981', bg: 'transparent' }
}
