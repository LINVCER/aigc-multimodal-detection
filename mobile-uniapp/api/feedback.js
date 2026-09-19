import { http, MOCK_MODE } from '@/utils/request'

/**
 * C 端提交反馈
 * @param {Object} payload
 * @param {'bug'|'suggestion'|'appeal'} payload.category
 * @param {string} payload.content 反馈内容（<=2000）
 * @param {number} [payload.taskId] 结果申诉时必填
 * @param {string} [payload.contact] 联系方式
 * @param {number} [payload.userId] W3.c 登录接入前透传
 * @returns {Promise<{id:number}>}
 */
export function submitFeedback(payload) {
  if (MOCK_MODE) return Promise.resolve({ id: Date.now() })
  return http({ url: '/api/v1/feedback', method: 'POST', data: payload })
}

/**
 * C 端我的反馈历史
 * 后端返 R<PageVO<FeedbackVO>>；request.js 已剥 R.data，这里再取 rows
 */
export function listMyFeedback(userId) {
  if (MOCK_MODE) {
    return Promise.resolve([
      {
        id: 2001, userId, category: 'appeal', taskId: 1,
        content: '第 3 段实际是我自己写的实验感想，但被判为高疑似 AI，请复核',
        contact: '138****5678', status: 'REPLIED',
        handledReply: '已核对，第 3 段确实句式较通用，模型误判；我们已加入 backlog 优化，本次不计入 AI 率。',
        handledAt: '2026-09-17 15:20:00',
        createdAt: '2026-09-16 14:22:00',
      },
      {
        id: 2000, userId, category: 'suggestion',
        content: '希望能支持一次上传多份论文批量检测',
        contact: '', status: 'PROCESSING',
        handledReply: null, handledAt: null,
        createdAt: '2026-09-15 09:44:00',
      },
      {
        id: 1999, userId, category: 'bug',
        content: '上传超过 15MB 的 word 有时候会 500，能否放宽或给更清晰的提示',
        contact: 'test@qq.com', status: 'PENDING',
        handledReply: null, handledAt: null,
        createdAt: '2026-09-13 20:11:00',
      },
    ])
  }
  return http({ url: '/api/v1/feedback/mine', data: { userId } })
    .then((d) => (Array.isArray(d) ? d : (d?.rows || [])))
}
