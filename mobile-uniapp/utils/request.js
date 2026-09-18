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
        if (!silent) uni.showToast({ title: '网络异常', icon: 'none' })
        reject(err)
      },
    })
  })
}
