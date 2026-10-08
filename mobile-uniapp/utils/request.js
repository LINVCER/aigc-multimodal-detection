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

// import.meta.env.XXX 由 Vite build 时静态替换成字面值；
// 早期用 `typeof import.meta !== 'undefined' && ...` 做防御，在微信小程序引擎里
// 会保留到运行时并触发 uni-app 对 `url` 模块的隐式 polyfill require，报
// `module 'utils/url.js' is not defined`。这里必须写"裸"的 import.meta.env.XXX。
// eslint-disable-next-line
export const API_BASE = import.meta.env.VITE_API_BASE || ''
// eslint-disable-next-line
export const MOCK_MODE = import.meta.env.VITE_USE_MOCK === 'true'

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

let redirecting = false
/** token 失效：清本地态、记住当前页，跳登录；并发多个 401 只跳一次 */
function redirectToLogin() {
  if (redirecting) return
  redirecting = true
  uni.removeStorageSync('access_token')
  try {
    const pages = getCurrentPages()
    const cur = pages[pages.length - 1]
    if (cur && cur.route && !cur.route.startsWith('pages/login/')) {
      const q = cur.options && Object.keys(cur.options).length
        ? '?' + Object.entries(cur.options).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&') : ''
      uni.setStorageSync('pending_login_redirect', '/' + cur.route + q)
    }
  } catch (e) { /* ignore */ }
  uni.showToast({ title: '登录已失效，请重新登录', icon: 'none' })
  setTimeout(() => { redirecting = false; uni.reLaunch({ url: '/pages/login/login' }) }, 600)
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
        if (auth && (res.statusCode === 401 || body?.code === 1401 || body?.code === 2401)) {
          redirectToLogin()
          reject(new Error(body?.msg || '登录已失效'))
          return
        }
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

/* ======================================================================
 * SSE 流式请求（论文检测助手 /api/v1/assistant/chat）
 *
 * 三条路径：
 *   MP-WEIXIN · uni.request({ enableChunked:true }) + requestTask.onChunkReceived（基础库 ≥ 2.20.1）
 *   H5        · fetch + ReadableStream
 *   其它 / 不支持 chunked · 退化为一次性请求，收到完整 body 后按帧回放
 * 服务端帧格式：`event: x\ndata: {json}\n\n`，这里做跨 chunk 的缓冲切帧。
 * ====================================================================== */

function makeSseParser(onEvent) {
  let buf = ''
  return {
    push(text) {
      buf += text
      let idx
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const frame = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        let event = 'message'
        const dataLines = []
        for (const line of frame.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
        }
        if (!dataLines.length) continue
        let data = dataLines.join('\n')
        try { data = JSON.parse(data) } catch (e) { /* 保持字符串 */ }
        onEvent(event, data)
      }
    },
    flush() { if (buf.trim()) { this.push('\n\n') } },
  }
}

function decodeChunk(chunk) {
  // 小程序给 ArrayBuffer；H5 给 Uint8Array
  const bytes = chunk instanceof ArrayBuffer ? new Uint8Array(chunk) : chunk
  if (typeof TextDecoder !== 'undefined') {
    decodeChunk._td = decodeChunk._td || new TextDecoder('utf-8')
    return decodeChunk._td.decode(bytes, { stream: true })
  }
  // 极老环境兜底：手工 utf-8 解码
  let s = ''
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i])
  try { return decodeURIComponent(escape(s)) } catch (e) { return s }
}

/**
 * 流式 POST
 * @param {object} opts { url, data, header, auth, onEvent(event, data), onError(err) }
 * @returns {{ abort(): void, done: Promise<void> }}
 */
export function httpStream(opts) {
  const { url, data, header = {}, auth = true, onEvent = () => {}, onError = () => {} } = opts
  if (auth) {
    const token = uni.getStorageSync('access_token')
    if (token) header.Authorization = `Bearer ${token}`
  }
  header['Content-Type'] = 'application/json'
  header.Accept = 'text/event-stream'
  const fullUrl = (API_BASE || '') + url
  const parser = makeSseParser(onEvent)
  let aborted = false
  let task = null
  let controller = null

  const done = new Promise((resolve) => {
    // #ifdef H5
    if (typeof fetch === 'function' && typeof ReadableStream !== 'undefined') {
      controller = typeof AbortController !== 'undefined' ? new AbortController() : null
      fetch(fullUrl, { method: 'POST', headers: header, body: JSON.stringify(data), signal: controller?.signal })
        .then(async (resp) => {
          if (!resp.ok || !resp.body) {
            onError(new Error(`HTTP ${resp.status}`))
            return
          }
          const reader = resp.body.getReader()
          for (;;) {
            const { value, done: end } = await reader.read()
            if (end) break
            parser.push(decodeChunk(value))
          }
          parser.flush()
        })
        .catch((err) => { if (!aborted) onError(err) })
        .finally(resolve)
      return
    }
    // #endif

    let gotChunk = false
    task = uni.request({
      url: fullUrl,
      method: 'POST',
      data,
      header,
      enableChunked: true,
      responseType: 'arraybuffer',
      timeout: 120_000,
      success: (res) => {
        // 不支持 chunked 的端会把完整 body 一次给到 success；已走过 onChunkReceived 的不重复回放
        if (!gotChunk && res.data) {
          const text = typeof res.data === 'string' ? res.data : decodeChunk(res.data)
          parser.push(text)
          parser.flush()
        }
      },
      fail: (err) => { if (!aborted) onError(new Error(classifyFailMsg(err))) },
      complete: resolve,
    })
    if (task && typeof task.onChunkReceived === 'function') {
      task.onChunkReceived((res) => {
        gotChunk = true
        parser.push(decodeChunk(res.data))
      })
    }
  })

  return {
    abort() {
      aborted = true
      try { controller?.abort() } catch (e) { /* ignore */ }
      try { task?.abort?.() } catch (e) { /* ignore */ }
    },
    done,
  }
}
