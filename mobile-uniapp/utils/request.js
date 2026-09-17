// 跨端请求封装（uni.request 而非 axios，兼容小程序）
// 环境变量约定：H5 走 vite import.meta.env.VITE_API_BASE；小程序走 manifest 里的编译常量或空字符串

// eslint-disable-next-line
const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE) || ''
export const MOCK_MODE = !API_BASE

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
