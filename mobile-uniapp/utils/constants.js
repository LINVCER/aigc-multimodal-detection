// Apple 语义色板（与 uni.scss 对齐；JS 侧需要引用色值时集中在此）
export const COLOR = {
  systemBlue:   '#007AFF',
  systemGreen:  '#34C759',
  systemOrange: '#FF9500',
  systemRed:    '#FF3B30',
  systemGray:   '#8E8E93',
  systemGray2:  '#AEAEB2',
  label:        '#000000',
  labelSecondary: 'rgba(60,60,67,0.60)',
  labelTertiary:  'rgba(60,60,67,0.30)',
  systemGroupedBackground: '#F2F2F7',
  systemBackground: '#FFFFFF',
  separator: 'rgba(60,60,67,0.29)',
}

export const STATUS_MAP = {
  PENDING: { text: '排队中', color: COLOR.systemGray,   bg: 'rgba(142,142,147,0.12)' },
  RUNNING: { text: '检测中', color: COLOR.systemOrange, bg: 'rgba(255,149,0,0.14)' },
  DONE:    { text: '已完成', color: COLOR.systemGreen,  bg: 'rgba(52,199,89,0.14)' },
  FAILED:  { text: '失败',   color: COLOR.systemRed,    bg: 'rgba(255,59,48,0.14)' },
}

// W3.b · 使用场景预设（取代原学位红线，对齐 Java SCENARIO_THRESHOLD）
export const SCENARIO_MAP = {
  academic_bachelor: { label: '学术·本科', threshold: 20, desc: '毕业论文自查' },
  academic_master:   { label: '学术·硕士', threshold: 15, desc: '硕士毕业论文' },
  academic_phd:      { label: '学术·博士', threshold: 10, desc: '博士毕业论文' },
  job_report:        { label: '职业报告',   threshold: 15, desc: '工作报告 / 项目文档' },
  self_media:        { label: '自媒体',     threshold: 30, desc: '公众号 / 小红书 / 头条' },
  other:             { label: '其他',       threshold: 25, desc: '通用文档' },
}

export const SOURCE_MAP = {
  human:    { label: '人类',       color: COLOR.systemGreen },
  gpt:      { label: 'GPT',        color: COLOR.systemPurple || '#AF52DE' },
  claude:   { label: 'Claude',     color: COLOR.systemPink   || '#FF2D55' },
  qwen:     { label: '通义千问',    color: COLOR.systemOrange },
  deepseek: { label: 'DeepSeek',   color: COLOR.systemBlue },
  glm:      { label: '智谱GLM',    color: COLOR.systemTeal   || '#5AC8FA' },
  kimi:     { label: 'Kimi',       color: '#AF52DE' },
  ernie:    { label: '文心',       color: COLOR.systemRed },
  other:    { label: '其他',       color: COLOR.systemGray },
}

export const STATUS_FILTER_OPTIONS = [
  { key: 'ALL',     text: '全部' },
  { key: 'RUNNING', text: '进行中' },
  { key: 'DONE',    text: '已完成' },
  { key: 'FAILED',  text: '失败' },
]

/**
 * AI 率相对红线的语义色
 * @param {number} rate 0-100
 * @param {number} threshold 红线
 */
export function aiRateColor(rate, threshold) {
  if (rate == null) return COLOR.systemGray
  if (rate <= threshold) return COLOR.systemGreen
  if (rate <= threshold * 1.5) return COLOR.systemOrange
  return COLOR.systemRed
}

export function paragraphRisk(prob) {
  if (prob >= 0.7) return { level: 'high',   color: COLOR.systemRed,    bg: 'rgba(255,59,48,0.14)' }
  if (prob >= 0.4) return { level: 'medium', color: COLOR.systemOrange, bg: 'rgba(255,149,0,0.16)' }
  return { level: 'low', color: COLOR.systemGreen, bg: 'transparent' }
}
