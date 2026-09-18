import { http } from './client'
import type { DetectTask, TaskDetail, PageResp, HumanizeResp } from './types'

/** §3.1 提交论文 */
export async function submitPaper(file: File, degreeType: string, title?: string): Promise<{ taskId: number; paperTitle: string; status: string; createdAt: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('degreeType', degreeType)
  if (title) form.append('title', title)
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
