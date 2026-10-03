import { http, httpStream, MOCK_MODE } from '@/utils/request'

/**
 * 论文检测助手 API —— 协议见 docs/design/202610-paper-assistant-agent-research.md §3.3
 * SSE 事件：meta / token / tool_call / tool_result / done / error
 */

/**
 * 发起一轮对话（流式）
 * @param {object} payload { message, conversationId?, taskId?, paragraphIdx?, userId?, clientContext? }
 * @param {object} handlers { onEvent(event, data), onError(err) }
 * @returns {{ abort(): void, done: Promise<void> }}
 */
export function chatStream(payload, handlers) {
  if (MOCK_MODE) return mockChat(payload, handlers)
  return httpStream({
    url: '/api/v1/assistant/chat',
    data: payload,
    onEvent: handlers.onEvent,
    onError: handlers.onError,
  })
}

/** 欢迎语 + 快捷问题 */
export function getQuickPrompts(taskId) {
  if (MOCK_MODE) {
    return Promise.resolve({
      welcome: taskId
        ? '我看了你这份报告。想先聊哪一段，还是先说说整体怎么看？'
        : '嗨，我是论文检测助手。检测结果看不懂、不知道怎么改、担心答辩被问，都可以直接问我。',
      prompts: taskId
        ? ['为什么这段像 AI？', '我这个 AI 率答辩会被卡吗？', '哪几段最该先改？', '我觉得判错了，怎么申诉？']
        : ['AI 率是怎么算出来的？', '我自己写的为什么会被判 AI？', '不同学校红线一样吗？', '怎么降低误判风险？'],
    })
  }
  return http({ url: '/api/v1/assistant/quick-prompts', data: taskId ? { taskId } : {} })
}

/** 会话列表 */
export function listConversations(userId, limit = 20) {
  if (MOCK_MODE) return Promise.resolve([])
  return http({ url: '/api/v1/assistant/conversations', data: { userId, limit } })
}

/** 会话详情 */
export function getConversation(conversationId) {
  return http({ url: `/api/v1/assistant/conversations/${conversationId}` })
}

/** 删除会话 */
export function deleteConversation(conversationId) {
  return http({ url: `/api/v1/assistant/conversations/${conversationId}`, method: 'DELETE' })
}

/* ---------------- mock：离线 UI 联调用，逐字回放一段固定回答 ---------------- */
function mockChat(payload, { onEvent }) {
  const cid = payload.conversationId || `mock-${Date.now()}`
  const text = '先别慌，这个数字只是「像 AI 的概率」，不是「抄袭」。你这篇整体 AI 率在红线以下，问题主要集中在第 3 段：句式太整齐、几乎没有第一人称和具体数据。你可以回忆一下当时实验里真实发生过什么，把那个细节写进去，会自然很多。'
  let i = 0
  let timer = null
  onEvent('meta', { conversationId: cid, model: 'mock', intent: 'explain' })
  const done = new Promise((resolve) => {
    timer = setInterval(() => {
      if (i >= text.length) {
        clearInterval(timer)
        onEvent('done', { finishReason: 'stop', usage: {}, tools: [], safety: 'pass' })
        resolve()
        return
      }
      onEvent('token', { delta: text.slice(i, i + 2) })
      i += 2
    }, 40)
  })
  return { abort() { clearInterval(timer) }, done }
}
