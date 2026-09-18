// 与 docs/design/API_CONTRACT.md 保持一致，字段全部 camelCase

export type TaskStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
/**
 * 使用场景（W3.b · 取代原 DegreeType）
 * 与后端 SCENARIO_THRESHOLD Map key 对齐
 */
export type Scenario =
  | 'academic_bachelor'
  | 'academic_master'
  | 'academic_phd'
  | 'job_report'
  | 'self_media'
  | 'other'

export interface DetectTask {
  id: number
  paperTitle: string
  status: TaskStatus
  aiRate: number | null
  scenario: Scenario
  threshold: number
  createdAt: string
  finishedAt?: string | null
  modelVersion?: string
}

export interface SentenceScore {
  sentenceIdx: number
  text: string
  aiProb: number
}

export interface ParagraphResult {
  paragraphIdx: number
  text: string
  aiProb: number | null           // excluded 段为 null
  calibratedProb: number | null
  confidenceInterval?: { lower: number; upper: number }
  sourceLabel: string | null
  warnings?: string[]
  sentences: SentenceScore[]
  excluded?: boolean              // 非正文（参考文献 / 图表 caption / 章节标题 等）
  excludeReason?: 'reference' | 'acknowledgement' | 'appendix' | 'sectionTitle' | 'caption'
  sectionName?: string            // 归属章节（摘要 / 引言 / 方法 / 参考文献 ...）
}

export interface TaskDetail extends DetectTask {
  paragraphs: ParagraphResult[]
  sourceLabels: Record<string, number>
}

export interface PageResp<T> {
  total: number
  rows: T[]
}

export interface UserInfo {
  id: number
  username: string
  realName: string
  role: string
  orgId: number
  orgName: string
}

export interface LoginResp {
  accessToken: string
  refreshToken: string
  expiresIn: number
  user: UserInfo
}

export interface HumanizeResp {
  humanizeTaskId: number
  originalText: string
  rewrittenText: string
  qualityScore: number
  modelVersion: string
}

/** Dashboard 统计（Wave 2.c）*/
export interface DailyTrendPoint {
  date: string          // YYYY-MM-DD
  count: number         // 当日检测量
  avgRate: number | null
}
export interface StatisticsResp {
  today: number
  thisMonth: number
  total: number
  done: number
  avgAiRate: number | null   // 整体平均 AI 率（DONE 任务）
  passRate: number | null    // 达标率 % (0-100)
  dailyTrend: DailyTrendPoint[]  // 长度 30，末位 = 今日
}
