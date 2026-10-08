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

/* =========== 平台账号（auth_user） =========== */

export type AccountRole = 'USER' | 'ADMIN' | 'OPS_ADMIN'

export interface AdminAccount {
  id: number
  username: string
  realName: string | null
  role: AccountRole
  orgName: string | null
  status: 0 | 1
  lastLoginAt: string | null
  createdAt: string
  detectCount: number
  lastDetectAt: string | null
}

export interface AccountStats { total: number; active: number; disabled: number; todayNew: number; active7d: number; byRole: Record<string, number> }

export async function getAccountStats(): Promise<AccountStats> {
  const resp = await http.get('/admin/account/stats')
  return resp.data.data
}

export async function getAccount(id: number): Promise<AdminAccount> {
  const resp = await http.get(`/admin/account/${id}`)
  return resp.data.data
}

export async function updateAccount(id: number, payload: { realName?: string; orgName?: string }): Promise<void> {
  await http.put(`/admin/account/${id}`, payload)
}

export async function batchAccountStatus(ids: number[], status: 0 | 1): Promise<{ updated: number }> {
  const resp = await http.post('/admin/account/batch-status', { ids, status })
  return resp.data.data
}

export async function listAccounts(params: { keyword?: string; role?: AccountRole; status?: 0 | 1; sortBy?: string; sortOrder?: 'asc' | 'desc'; pageNum?: number; pageSize?: number } = {}): Promise<{ total: number; rows: AdminAccount[] }> {
  const resp = await http.get('/admin/account/list', { params: { pageNum: 1, pageSize: 20, ...params } })
  return resp.data.data
}

export async function setAccountStatus(id: number, status: 0 | 1): Promise<void> {
  await http.post(`/admin/account/${id}/status`, null, { params: { status } })
}

export async function resetAccountPassword(id: number): Promise<{ tempPassword: string }> {
  const resp = await http.post(`/admin/account/${id}/reset-password`)
  return resp.data.data
}

export async function setAccountRole(id: number, role: AccountRole): Promise<void> {
  await http.post(`/admin/account/${id}/role`, null, { params: { role } })
}

export async function createAccount(payload: { username: string; realName?: string; role?: AccountRole; orgName?: string }): Promise<{ tempPassword: string }> {
  const resp = await http.post('/admin/account', payload)
  return resp.data.data
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
  rateBucket?: string
  pass?: boolean
  modelVersion?: string
  dateFrom?: string
  dateTo?: string
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

/* =========== 对话质检（增长闭环 §3） =========== */

export type QualityTag = 'good' | 'wrong_fact' | 'off_point' | 'boundary' | 'tone'

export interface ConversationRow {
  conversationId: string
  userId: number | null
  taskId: number | null
  title: string
  turns: number
  boundaryCount: number
  intents: string[]
  noteCount: number
  updatedAt: string
}

export interface ConversationDetail {
  conversation: { conversationId: string; userId: number | null; taskId: number | null; title: string; messages: Array<{ role: string; content: string; ts?: number; tools?: any[]; blocked?: boolean }>; updatedAt: string }
  logs: Array<{ id: number; question: string; answer: string; intent: string; tools: string | null; boundaryFlag: boolean; boundaryType: string | null; kbTopScore: number | null; kbTopRef: string | null; latencyMs: number | null; createdAt: string }>
  notes: Array<{ id: number; logId: number | null; score: number | null; tag: QualityTag; note: string | null; createdAt: string }>
}

export async function listAssistantConversations(params: { days?: number; boundaryOnly?: boolean; limit?: number }): Promise<ConversationRow[]> {
  const resp = await http.get('/admin/assistant/conversations', { params })
  return resp.data.data
}

export async function getAssistantConversation(cid: string): Promise<ConversationDetail> {
  const resp = await http.get(`/admin/assistant/conversations/${cid}`)
  return resp.data.data
}

export async function addQualityNote(payload: { conversationId: string; logId?: number; score?: number; tag: QualityTag; note?: string }): Promise<{ id: number }> {
  const resp = await http.post('/admin/assistant/quality-notes', payload)
  return resp.data.data
}

export async function getQualityStats(days = 30): Promise<{ days: number; total: number; tags: Record<string, number>; avgScore: number | null }> {
  const resp = await http.get('/admin/assistant/quality-notes/stats', { params: { days } })
  return resp.data.data
}

/* =========== 检测分析（detect-analytics-plan） =========== */

export interface DetectAnalytics {
  from: string
  to: string
  scenario: string
  status: string
  kpi: { total: number; done: number; avgAiRate: number | null; passRate: number | null; overRate: number | null }
  trend: Array<{ date: string; total: number; done: number; avgAiRate: number | null; pass: number; over: number }>
  scenarioDist: Record<string, number>
  statusDist: Record<string, number>
  rateBuckets: Record<string, number>
  sourceDist: Record<string, number>
}

export async function getDetectAnalytics(params: { dateFrom?: string; dateTo?: string; scenario?: string; status?: string }): Promise<DetectAnalytics> {
  const resp = await http.get('/admin/detect/analytics', { params })
  return resp.data.data
}

export async function rebuildDetectStatistics(days = 0): Promise<{ rows: number; days: number }> {
  const resp = await http.post('/admin/detect/statistics/rebuild', null, { params: { days } })
  return resp.data.data
}
