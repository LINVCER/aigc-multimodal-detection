// 跨端请求封装（uni.request 而非 axios，兼容小程序）
//
// 语义（修复自：原逻辑 MOCK_MODE=!API_BASE 造成默认永远走 mock，登录后一切不联后端）：
//   API_BASE      · 请求前缀。H5 dev 场景保持空串（走 manifest.json 里 vite proxy），
//                   真实域名部署或直连后端时填绝对地址
//   MOCK_MODE     · 显式开关。VITE_USE_MOCK=true 时启用离线 mock；默认关，走真实 HTTP
//
// 三种典型场景：
//   1) H5 dev + vite proxy：不配任何 env → API_BASE='' + MOCK_MODE=false → 请求 /api/* 走 proxy
//   2) 直连远程后端：VITE_API_BASE=https://api.xxx.com + MOCK_MODE=false → 请求带绝对前缀
//   3) 纯 UI 离线联调：VITE_USE_MOCK=true → 所有 http()/uploadFile 走内置 mock 数据

// eslint-disable-next-line
export const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE) || ''
// eslint-disable-next-line
export const MOCK_MODE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_USE_MOCK) === 'true'

/**
 * uni.request fail 语义分类：
 *   errMsg 含 timeout    → "请求超时"
 *   errMsg 含 abort      → "已取消"
 *   fail   / SSL / DNS   → "网络异常，请检查连接"
 *   其它                 → 原 errMsg
 * 上层不再重复弹 toast（fail 一律已弹）。
 */
function classifyFailMsg(err) {
  const raw = String(err?.errMsg || err?.message || '')
  if (!raw) return '网络异常'
  if (raw.includes('timeout')) return '请求超时，请稍后重试'
  if (raw.includes('abort'))   return '请求已取消'
  if (raw.includes('fail'))    return '网络异常，请检查连接'
  return raw
}

/**
 * 统一 HTTP 请求
 * @param {object} opts uni.request 原参数 + { auth: 是否携带 token, silent: 是否静默失败 }
 * @returns Promise<data>
 */
export function http(opts) {
  const { url, method = 'GET', data, header = {}, auth = true, silent = false } = opts

  if (auth) {
    const token = uni.getStorageSync('access_token')
    if (token) header.Authorization = `Bearer ${token}`
  }

  return new Promise((resolve, reject) => {
    uni.request({
      url: (API_BASE || '') + url,
      method,
      data,
      header,
      timeout: 30_000,
      success: (res) => {
        // 若依 R 结构：{ code, msg, data }；code=200 或 0 为成功
        const body = res.data
        if (body && typeof body.code === 'number' && body.code !== 0 && body.code !== 200) {
          if (!silent) uni.showToast({ title: body.msg || '请求失败', icon: 'none' })
          reject(new Error(body.msg || 'request failed'))
          return
        }
        resolve(body?.data ?? body)
      },
      fail: (err) => {
        // 按 errMsg 区分 timeout / 断连，避免上层再弹造成双重 toast
        const msg = classifyFailMsg(err)
        if (!silent) uni.showToast({ title: msg, icon: 'none' })
        const e = new Error(msg)
        e.raw = err
        reject(e)
      },
    })
  })
}
