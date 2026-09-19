import { API_BASE, MOCK_MODE } from '@/utils/request'

/**
 * 下载检测报告 PDF · 后端 GET /api/v1/report/tasks/{id}/pdf 返 PDF binary
 *
 * H5 端：fetch blob → createObjectURL → anchor download 触发浏览器下载
 * 小程序端：uni.downloadFile → uni.openDocument（PDF 预览 + 微信 openMenu 保存到本地）
 *
 * @param {number|string} taskId 任务 ID
 * @param {string} [paperTitle] 论文标题（生成的文件名 · 默认「AIGC检测报告-{taskId}.pdf」）
 * @returns Promise<void>
 */
export function downloadReportPdf(taskId, paperTitle) {
  if (MOCK_MODE) {
    uni.showToast({ title: '离线模式无法下载 PDF', icon: 'none' })
    return Promise.resolve()
  }
  const url = (API_BASE || '') + `/api/v1/report/tasks/${taskId}/pdf`
  const token = uni.getStorageSync('access_token')
  const header = token ? { Authorization: `Bearer ${token}` } : {}
  const safeTitle = (paperTitle || `AIGC检测报告-${taskId}`).replace(/[\\/:*?"<>|]/g, '_')

  // #ifdef H5
  return fetch(url, { headers: header }).then(async (resp) => {
    if (!resp.ok) throw new Error(`下载失败：HTTP ${resp.status}`)
    const blob = await resp.blob()
    const objectUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = objectUrl
    a.download = `${safeTitle}.pdf`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
  })
  // #endif

  // #ifndef H5
  return new Promise((resolve, reject) => {
    uni.showLoading({ title: '下载中…', mask: true })
    uni.downloadFile({
      url, header,
      success: (res) => {
        uni.hideLoading()
        if (res.statusCode !== 200) {
          uni.showToast({ title: `下载失败：HTTP ${res.statusCode}`, icon: 'none' })
          return reject(new Error(`HTTP ${res.statusCode}`))
        }
        // 唤起 PDF 预览 · 用户可在右上角"..."保存到本地/发给好友
        uni.openDocument({
          filePath: res.tempFilePath,
          fileType: 'pdf',
          showMenu: true,
          success: () => resolve(),
          fail: (err) => {
            uni.showToast({ title: '打开失败，请稍后重试', icon: 'none' })
            reject(err)
          },
        })
      },
      fail: (err) => {
        uni.hideLoading()
        uni.showToast({ title: '下载失败，请检查网络', icon: 'none' })
        reject(err)
      },
    })
  })
  // #endif
}
