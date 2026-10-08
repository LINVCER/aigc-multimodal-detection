import { http, API_BASE } from './client'

export type FeedbackCategory = 'bug' | 'suggestion' | 'appeal'
export type FeedbackStatus = 'PENDING' | 'PROCESSING' | 'REPLIED' | 'IGNORED'

export interface FeedbackItem {
  id: number
  userId?: number | null
  category: FeedbackCategory
  taskId?: number | null
  paragraphIdxs?: number[] | null
  consentImprove?: boolean | null
  content: string
  contact?: string | null
  status: FeedbackStatus
  handledBy?: number | null
  handledReply?: string | null
  handledAt?: string | null
  createdAt: string
}

export interface SubmitFeedbackPayload {
  category: FeedbackCategory
  content: string
  taskId?: number
  /** 申诉勾选「判错了」的段落序号；空表示整体申诉 */
  paragraphIdxs?: number[]
  /** 同意勾选段落用于改进模型（只进评测集） */
  consentImprove?: boolean
  contact?: string
  /** W3.c 登录接入前暂从上下文透传，登录接入后后端从 Sa-Token 取 */
  userId?: number
}

/* =========== 误判样本池（增长闭环 §2.2） =========== */

export type HardSampleVerdict = 'confirm_fp' | 'confirm_tp' | 'unsure'

export interface HardSample {
  id: number
  feedbackId: number | null
  taskId: number
  paragraphIdx: number
  textSha256: string
  /** 仅用户授权时有 */
  text: string | null
  modelProb: number | null
  modelVersion: string
  userLabel: string
  opsVerdict: HardSampleVerdict | null
  source: string
  scenario: string | null
  reviewedAt: string | null
  createdAt: string
}

/** 某条申诉勾选段落对应的样本 */
export async function listFeedbackSamples(feedbackId: number): Promise<HardSample[]> {
  const resp = await http.get(`/admin/feedback/${feedbackId}/samples`)
  return resp.data.data
}

/** 运营复核 */
export async function setHardSampleVerdict(sampleId: number, value: HardSampleVerdict): Promise<void> {
  await http.post(`/admin/hard-samples/${sampleId}/verdict`, null, { params: { value } })
}

/** 样本池列表 */
export async function listHardSamples(params: { verdict?: string; days?: number; limit?: number } = {}): Promise<HardSample[]> {
  const resp = await http.get('/admin/hard-samples', { params })
  return resp.data.data
}

/** 导出 JSONL 的地址（浏览器直接打开下载） */
export function hardSampleExportUrl(verdicts = 'confirm_fp,confirm_tp'): string {
  return `${API_BASE}/admin/hard-samples/export?verdicts=${encodeURIComponent(verdicts)}`
}

/** C 端提交反馈 */
export async function submitFeedback(payload: SubmitFeedbackPayload): Promise<{ id: number }> {
  const resp = await http.post('/api/v1/feedback', payload)
  return resp.data.data
}

/** C 端查自己的反馈历史 */
export async function listMyFeedback(userId: number): Promise<FeedbackItem[]> {
  const resp = await http.get('/api/v1/feedback/mine', { params: { userId } })
  return resp.data.data
}

export interface FeedbackStats { total: number; byStatus: Record<string, number>; byCategory: Record<string, number>; todayNew: number; pendingAppeal: number }

export async function getFeedbackStats(): Promise<FeedbackStats> {
  const resp = await http.get('/admin/feedback/stats')
  return resp.data.data
}

export async function batchHandleFeedback(ids: number[], status: FeedbackStatus, reply?: string): Promise<{ updated: number }> {
  const resp = await http.post('/admin/feedback/batch-handle', { ids, status, reply })
  return resp.data.data
}

/** 运营后台列表（W3.e 后台页面调用） */
export async function listFeedbackAdmin(params: {
  status?: FeedbackStatus | ''
  category?: FeedbackCategory | ''
  keyword?: string
  taskId?: number
  dateFrom?: string
  dateTo?: string
  pageNum?: number
  pageSize?: number
} = {}): Promise<{ total: number; rows: FeedbackItem[] }> {
  const resp = await http.get('/admin/feedback/list', {
    params: { pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}

/** 运营后台回复/处置 */
export async function handleFeedback(
  id: number,
  payload: { status?: FeedbackStatus; reply?: string; handledBy?: number },
): Promise<void> {
  await http.post(`/admin/feedback/${id}/handle`, payload)
}
