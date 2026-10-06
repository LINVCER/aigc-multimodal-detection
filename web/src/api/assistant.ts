import { http, API_BASE } from './client'

/**
 * 论文检测助手 API —— 协议见 docs/design/202610-paper-assistant-agent-research.md §3.3
 * SSE 事件：meta / token / tool_call / tool_result / done / error
 */

export type AssistantEvent = 'meta' | 'token' | 'tool_call' | 'tool_result' | 'done' | 'error' | string

export interface ChatPayload {
  message: string
  conversationId?: string
  taskId?: number
  paragraphIdx?: number
  userId?: number
  clientContext?: Record<string, unknown>
}

export interface ChatHandlers {
  onEvent: (event: AssistantEvent, data: any) => void
  onError: (err: Error) => void
}

export interface ChatHandle {
  abort: () => void
  done: Promise<void>
}

export interface QuickPrompts {
  welcome: string
  prompts: string[]
}

/** 发起一轮对话（fetch + ReadableStream，按 `\n\n` 切帧） */
export function chatStream(payload: ChatPayload, handlers: ChatHandlers): ChatHandle {
  const controller = new AbortController()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  const token = localStorage.getItem('access_token')
  if (token) headers.Authorization = `Bearer ${token}`

  const done = (async () => {
    try {
      const resp = await fetch(`${API_BASE}/api/v1/assistant/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload),
        signal: controller.signal,
      })
      if (!resp.ok || !resp.body) {
        handlers.onError(new Error(`HTTP ${resp.status}`))
        return
      }
      const reader = resp.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buf = ''
      const emitFrames = () => {
        let idx: number
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const frame = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          let event: string = 'message'
          const dataLines: string[] = []
          for (const line of frame.split('\n')) {
            if (line.startsWith('event:')) event = line.slice(6).trim()
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
          }
          if (!dataLines.length) continue
          let data: any = dataLines.join('\n')
          try { data = JSON.parse(data) } catch { /* 保持字符串 */ }
          handlers.onEvent(event, data)
        }
      }
      for (;;) {
        const { value, done: end } = await reader.read()
        if (end) break
        buf += decoder.decode(value, { stream: true })
        emitFrames()
      }
      if (buf.trim()) { buf += '\n\n'; emitFrames() }
    } catch (e: any) {
      if (e?.name !== 'AbortError') handlers.onError(e instanceof Error ? e : new Error(String(e)))
    }
  })()

  return { abort: () => controller.abort(), done }
}

/** 欢迎语 + 快捷问题 */
export async function getQuickPrompts(taskId?: number): Promise<QuickPrompts> {
  const { data } = await http.get('/api/v1/assistant/quick-prompts', { params: taskId ? { taskId } : {} })
  return data.data as QuickPrompts
}

/** 会话列表 */
export async function listConversations(userId?: number, limit = 20) {
  const { data } = await http.get('/api/v1/assistant/conversations', { params: { userId, limit } })
  return data.data as Array<{ conversationId: string; title: string; taskId?: number; updatedAt: string; turns: number }>
}

/** 会话详情（历史消息，用于恢复对话） */
export async function getConversation(conversationId: string) {
  const { data } = await http.get(`/api/v1/assistant/conversations/${conversationId}`)
  return data.data as {
    conversationId: string
    taskId?: number | null
    messages: Array<{ role: string; content: string; ts?: number }>
  }
}

/** 删除会话 */
export async function deleteConversation(conversationId: string): Promise<void> {
  await http.delete(`/api/v1/assistant/conversations/${conversationId}`)
}
