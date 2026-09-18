import { http } from './client'

export type FeedbackCategory = 'bug' | 'suggestion' | 'appeal'
export type FeedbackStatus = 'PENDING' | 'PROCESSING' | 'REPLIED' | 'IGNORED'

export interface FeedbackItem {
  id: number
  userId?: number | null
  category: FeedbackCategory
  taskId?: number | null
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
  contact?: string
  /** W3.c 登录接入前暂从上下文透传，登录接入后后端从 Sa-Token 取 */
  userId?: number
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

/** 运营后台列表（W3.e 后台页面调用） */
export async function listFeedbackAdmin(params: {
  status?: FeedbackStatus | ''
  keyword?: string
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
