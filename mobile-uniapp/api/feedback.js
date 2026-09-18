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

/** C 端历史 */
export function listMyFeedback(userId) {
  if (MOCK_MODE) return Promise.resolve([])
  return http({ url: '/api/v1/feedback/mine', data: { userId } })
}
