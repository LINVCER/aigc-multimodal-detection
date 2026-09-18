import { http } from './client'
import type { DetectTask, TaskDetail, PageResp, HumanizeResp, SentenceScore, StatisticsResp } from './types'

/** §3.1 提交论文（W3.b · scenario；W3.c 前透传 userId 便于后台 topUsers/userLabel 归属） */
export async function submitPaper(
  file: File,
  scenario: string,
  title?: string,
  userId?: number | string,
): Promise<{ taskId: number; paperTitle: string; status: string; createdAt: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('scenario', scenario)
  if (title) form.append('title', title)
  if (userId != null && userId !== '') form.append('userId', String(userId))
  const resp = await http.post('/api/v1/detect/submit', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return resp.data.data
}

/** §3.2 任务列表 */
export async function listTasks(params: { pageNum?: number; pageSize?: number; status?: string; keyword?: string } = {}): Promise<PageResp<DetectTask>> {
  const resp = await http.get('/api/v1/detect/tasks', {
    params: { pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}

/** §3.3 任务详情 */
export async function getTaskDetail(id: number): Promise<TaskDetail> {
  const resp = await http.get(`/api/v1/detect/tasks/${id}`)
  return resp.data.data
}

/** §3.4 重试 */
export async function retryTask(id: number): Promise<TaskDetail> {
  const resp = await http.post(`/api/v1/detect/tasks/${id}/retry`)
  return resp.data.data
}

/** §3.5 取消 */
export async function cancelTask(id: number): Promise<void> {
  await http.post(`/api/v1/detect/tasks/${id}/cancel`)
}

/** §3.6 删除 */
export async function deleteTask(id: number): Promise<void> {
  await http.delete(`/api/v1/detect/tasks/${id}`)
}

/** §4 降 AIGC */
export async function requestHumanize(taskId: number, paragraphIdx: number, style = 'academic'): Promise<HumanizeResp> {
  const resp = await http.post('/api/v1/humanize', { taskId, paragraphIdx, style })
  return resp.data.data
}

/**
 * §8.2 直接文本检测（不生成任务）· Wave 1 · 1.4 文本粘贴
 * 返回段落级 + 句子级打分，前端内联展示
 */
export interface DirectDetectResp {
  aiProb: number
  calibratedProb: number
  riskLevel: 'low' | 'medium' | 'high'
  warning?: string
  branchScores?: Record<string, number>
  sentences: SentenceScore[]
}

export async function detectTextDirect(text: string): Promise<DirectDetectResp> {
  const resp = await http.post('/api/v1/detect/paragraph', { text, returnSentences: true })
  const d = resp.data.data || {}
  return {
    aiProb: d.ai_prob ?? d.aiProb ?? 0,
    calibratedProb: d.calibrated_prob ?? d.calibratedProb ?? 0,
    riskLevel: d.risk_level ?? d.riskLevel ?? 'low',
    warning: d.warning || undefined,
    branchScores: d.branch_scores || d.branchScores,
    sentences: (d.sentences || []).map((s: any) => ({
      sentenceIdx: s.sentence_idx ?? s.sentenceIdx,
      text: text.substring(s.offset_start ?? 0, Math.min(s.offset_end ?? text.length, text.length)),
      aiProb: s.ai_prob ?? s.aiProb,
    })),
  }
}

/** §3.7 Dashboard 统计（Wave 2.c） */
export async function getStatistics(): Promise<StatisticsResp> {
  const resp = await http.get('/api/v1/detect/statistics')
  return resp.data.data
}

/**
 * §5 下载 PDF 报告（Wave 1 · 1.1）
 * 用 axios responseType blob 拿二进制，浏览器 saveAs 触发下载
 */
export async function downloadReportPdf(taskId: number, paperTitle: string): Promise<void> {
  const resp = await http.get(`/api/v1/report/tasks/${taskId}/pdf`, {
    responseType: 'blob',
  })
  const blob = new Blob([resp.data], { type: 'application/pdf' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `AIGC检测报告-${paperTitle}.pdf`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
