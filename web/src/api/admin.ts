import { http } from './client'

/* =========== §3.1 Dashboard =========== */

export interface DashboardKpi {
  todayNewUser: number
  todayDetect: number
  totalUser: number
  totalDetect: number
  avgAiRate: number
}
export interface DashboardTrendRow {
  date: string
  newUser: number
  detect: number
  avgAiRate: number
}
export interface DashboardResp {
  kpi: DashboardKpi
  trend: DashboardTrendRow[]
  scenarioDist: Record<string, number>
  topUsers: Array<{ userId: number; userLabel: string; detectCount: number }>
  pendingFeedback: Array<any>
}

export async function getAdminDashboard(): Promise<DashboardResp> {
  const resp = await http.get('/admin/dashboard')
  return resp.data.data
}

/* =========== §3.2 用户列表 =========== */

export type LoginType = 'phone' | 'wechat' | 'email'
export type UserStatus = 'NORMAL' | 'BANNED' | 'INACTIVE' | 'SUSPICIOUS'

export interface AdminUser {
  id: number
  loginType: LoginType
  identity: string
  detectCount: number
  lastLoginAt: string
  registeredAt: string
  status: UserStatus
}

export async function listAdminUsers(params: {
  loginType?: LoginType | ''
  status?: UserStatus | ''
  keyword?: string
  minDetect?: number
  maxDetect?: number
  pageNum?: number
  pageSize?: number
} = {}): Promise<{ total: number; rows: AdminUser[] }> {
  const resp = await http.get('/admin/user/list', {
    params: { pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}

export async function banUser(id: number): Promise<void> {
  await http.post(`/admin/user/${id}/ban`)
}

export async function unbanUser(id: number): Promise<void> {
  await http.post(`/admin/user/${id}/unban`)
}

/* =========== §3.4 全平台任务列表 =========== */

export interface AdminTask {
  id: number
  paperTitle: string
  scenario: string
  threshold: number
  aiRate: number | null
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
  createdAt: string
  wordCount: number | null
  modelVersion: string
  userId: number | null
  userLabel: string
}

export async function listAdminTasks(params: {
  status?: string
  scenario?: string
  userId?: number
  keyword?: string
  minAiRate?: number
  maxAiRate?: number
  pageNum?: number
  pageSize?: number
} = {}): Promise<{ total: number; rows: AdminTask[] }> {
  const resp = await http.get('/admin/task/list', {
    params: { pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}

/* =========== 助手运营（增长闭环 P0） =========== */

export interface AssistantStats {
  days: number
  conversations: number
  users: number
  intents: Record<string, number>
  boundaryRate: number | null
  boundaryTypes: Record<string, number>
  kbHitRate: number | null
  kbSample: number
  toolFailedRate: number | null
  errorRate: number | null
  promptTokens: number
  completionTokens: number
}

export interface KnowledgeGap {
  id: number
  question: string
  intent: string
  kbTopScore: number | null
  kbTopRef: string | null
  conversationId: string
  createdAt: string
}

export interface KnowledgeChunkRow {
  id: number
  doc: string
  title: string
  tags: string
  bodyPreview: string
  sortOrder: number
  enabled: boolean
  updatedAt: string
}

export interface KnowledgeChunkDetail extends Omit<KnowledgeChunkRow, 'bodyPreview'> {
  body: string
  createdAt: string
}

export interface KnowledgeChunkPayload {
  doc?: string
  title: string
  tags?: string
  body: string
  sortOrder?: number
  enabled?: boolean
  fromLogId?: number
}

export interface KnowledgeDraft extends KnowledgeChunkPayload {
  kbTopRef?: string | null
}

export interface ReloadResult { ok?: boolean; chunks?: number; error?: string }

export async function getAssistantStats(days = 7, threshold = 1.0): Promise<AssistantStats> {
  const resp = await http.get('/admin/assistant/stats', { params: { days, threshold } })
  return resp.data.data
}

export async function listKnowledgeGaps(params: { days?: number; threshold?: number; limit?: number }): Promise<KnowledgeGap[]> {
  const resp = await http.get('/admin/assistant/knowledge-gaps', { params })
  return resp.data.data
}

export async function getKnowledgeGapDraft(logId: number): Promise<KnowledgeDraft> {
  const resp = await http.get(`/admin/assistant/knowledge-gaps/${logId}/draft`)
  return resp.data.data
}

export async function listKnowledge(params: { doc?: string; keyword?: string; enabled?: boolean }): Promise<KnowledgeChunkRow[]> {
  const resp = await http.get('/admin/assistant/knowledge', { params })
  return resp.data.data
}

export async function getKnowledge(id: number): Promise<KnowledgeChunkDetail> {
  const resp = await http.get(`/admin/assistant/knowledge/${id}`)
  return resp.data.data
}

export async function createKnowledge(payload: KnowledgeChunkPayload): Promise<{ id: number; reload: ReloadResult }> {
  const resp = await http.post('/admin/assistant/knowledge', payload)
  return resp.data.data
}

export async function updateKnowledge(id: number, payload: KnowledgeChunkPayload): Promise<{ id: number; reload: ReloadResult }> {
  const resp = await http.put(`/admin/assistant/knowledge/${id}`, payload)
  return resp.data.data
}

export async function setKnowledgeEnabled(id: number, enabled: boolean): Promise<ReloadResult> {
  const resp = await http.post(`/admin/assistant/knowledge/${id}/enabled`, null, { params: { enabled } })
  return resp.data.data
}

export async function reloadKnowledge(): Promise<ReloadResult> {
  const resp = await http.post('/admin/assistant/knowledge/reload')
  return resp.data.data
}
