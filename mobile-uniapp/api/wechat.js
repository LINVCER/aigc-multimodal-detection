import { http, MOCK_MODE } from '@/utils/request'

/**
 * 微信 · 保存用户授权的订阅消息模板 ID（Wave 3.3）
 *
 * 上层流程（小程序端）：
 *   1) uni.requestSubscribeMessage({ tmplIds }) 拉起授权
 *   2) 用户选择接受的模板 → 前端过滤 status === 'accept' 的 tmplIds
 *   3) 调本接口把 accepted 的模板 ID 存到后端
 *   4) 后端在检测完成时用 wx 服务端 subscribeMessage.send 推送
 *
 * @param {{tmplIds: string[]}} payload
 */
export function saveSubscribeTemplate(payload) {
  if (MOCK_MODE) return Promise.resolve()
  return http({
    url: '/api/v1/auth/wechat/subscribe',
    method: 'POST',
    data: payload,
  })
}

/**
 * 便捷封装：请求订阅授权 → 存后端
 * 用于 upload/text.vue upload/audio.vue 提交成功后调用
 * @param {string[]} tmplIds 要请求授权的模板 ID 列表
 * @returns Promise<string[]> · accepted 的 tmplIds
 */
export function requestAndSaveSubscribe(tmplIds) {
  return new Promise((resolve) => {
    // #ifdef MP-WEIXIN
    uni.requestSubscribeMessage({
      tmplIds,
      success: async (res) => {
        const accepted = tmplIds.filter((id) => res[id] === 'accept')
        if (accepted.length) {
          try { await saveSubscribeTemplate({ tmplIds: accepted }) } catch (e) { /* silent */ }
        }
        resolve(accepted)
      },
      fail: () => resolve([]),
    })
    // #endif

    // #ifndef MP-WEIXIN
    // H5 / App 端不支持微信订阅消息，静默 resolve
    resolve([])
    // #endif
  })
}
