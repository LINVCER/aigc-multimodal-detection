// 与 docs/design/API_CONTRACT.md 保持一致，字段全部 camelCase

export type TaskStatus = 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
export type DegreeType = 'BACHELOR' | 'MASTER' | 'PHD'

export interface DetectTask {
  id: number
  paperTitle: string
  status: TaskStatus
  aiRate: number | null
  degreeType: DegreeType
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
  aiProb: number
  calibratedProb: number
  confidenceInterval?: { lower: number; upper: number }
  sourceLabel: string | null
  warnings?: string[]
  sentences: SentenceScore[]
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
