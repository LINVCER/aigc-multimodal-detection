import { http, MOCK_MODE, API_BASE } from '@/utils/request'

// ---- mock 数据（未配 VITE_API_BASE 时启用，供离线 UI 联调）----

const mockTasks = [
  { id: 1, paperTitle: '基于深度学习的中文文本情感分析研究', status: 'DONE',    aiRate: 26.4, scenario: 'academic_master',   threshold: 15, createdAt: '2026-09-16 14:20' },
  { id: 2, paperTitle: '乡村振兴背景下农产品电商发展路径研究', status: 'RUNNING', aiRate: null, scenario: 'academic_bachelor', threshold: 20, createdAt: '2026-09-17 09:12' },
  { id: 3, paperTitle: '双碳目标下制造业绿色转型机制研究',   status: 'DONE',    aiRate: 8.1,  scenario: 'academic_phd',      threshold: 10, createdAt: '2026-09-15 18:44' },
]

const mockDetail = {
  ...mockTasks[0],
  sourceLabels: { qwen: 0.42, gpt: 0.31, human: 0.27 },
  paragraphs: [
    {
      paragraphIdx: 0,
      text: '随着人工智能技术的快速发展，深度学习在自然语言处理领域的应用日益广泛。值得注意的是，情感分析作为其中的重要分支，已经成为学术界和工业界共同关注的焦点。',
      aiProb: 0.91, calibratedProb: 0.88, sourceLabel: 'qwen',
      sentences: [
        { sentenceIdx: 0, text: '随着人工智能技术的快速发展，深度学习在自然语言处理领域的应用日益广泛。', aiProb: 0.93 },
        { sentenceIdx: 1, text: '值得注意的是，情感分析作为其中的重要分支，已经成为学术界和工业界共同关注的焦点。', aiProb: 0.89 },
      ],
    },
    {
      paragraphIdx: 1,
      text: '我们在实验中发现，当训练数据里混入大量口语化评论时，模型在正式文本上的表现反而下降了两个点，这个现象起初让我们很困惑。',
      aiProb: 0.12, calibratedProb: 0.09, sourceLabel: 'human',
      sentences: [
        { sentenceIdx: 0, text: '我们在实验中发现，当训练数据里混入大量口语化评论时，模型在正式文本上的表现反而下降了两个点，这个现象起初让我们很困惑。', aiProb: 0.12 },
      ],
    },
  ],
}

// ---- API ----
// 路径遵循 docs/design/API_CONTRACT.md（§3-§4），移除 /mobile 前缀，与 Web 端共用

export function listTasks() {
  if (MOCK_MODE) return Promise.resolve(mockTasks)
  // §3.2 分页响应 { total, rows }，request.js 已剥出 data，这里再取 rows
  return http({
    url: '/api/v1/detect/tasks',
    data: { pageNum: 1, pageSize: 50 },
  }).then((d) => d.rows || d)
}

export function getTaskDetail(id) {
  if (MOCK_MODE) return Promise.resolve({ ...mockDetail, id })
  return http({ url: `/api/v1/detect/tasks/${id}` })
}

/**
 * 上传检测（支持 text/audio/image 多模态）
 * @param {string} filePath 本地文件路径
 * @param {string} name 文件名
 * @param {string} scenario academic_bachelor|academic_master|academic_phd|job_report|self_media|other
 * @param {number|string} [userId] 登录用户 ID（未登录可空）
 * @param {string} [modality] text|audio|image；不传后端按后缀猜
 * @returns { id, paperTitle, status, createdAt }
 */
export function uploadPaper(filePath, name, scenario, userId, modality) {
  if (MOCK_MODE) {
    return Promise.resolve({
      id: Date.now(),
      paperTitle: name,
      status: 'PENDING',
      modality: modality || 'text',
      scenario,
      threshold: 20,
      createdAt: new Date().toISOString(),
    })
  }
  return new Promise((resolve, reject) => {
    const token = uni.getStorageSync('access_token')
    const formData = { scenario }
    if (userId != null && userId !== '') formData.userId = String(userId)
    if (modality) formData.modality = modality
    uni.uploadFile({
      // §3.1 上传端点 · 必须拼 API_BASE，否则 H5 打到当前源（5175）404
      // H5 dev 场景 API_BASE 为空 → 相对 /api/v1/... 走 manifest.json 里 vite proxy
      url: (API_BASE || '') + '/api/v1/detect/submit',
      filePath,
      name: 'file',
      formData,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        try {
          const body = JSON.parse(res.data)
          if (body.code !== 0 && body.code !== 200) return reject(new Error(body.msg))
          // 契约 §3.1 字段名 taskId → 前端统一 id，避免上层跳转空值
          const d = body.data || {}
          resolve({
            id: d.taskId || d.id,
            paperTitle: d.paperTitle || name,
            status: d.status || 'PENDING',
            createdAt: d.createdAt,
          })
        } catch (e) { reject(e) }
      },
      fail: reject,
    })
  })
}

/**
 * §3.4 重试失败任务
 */
export function retryTask(id) {
  if (MOCK_MODE) return Promise.resolve({ id, status: 'PENDING' })
  return http({ url: `/api/v1/detect/tasks/${id}/retry`, method: 'POST' })
}

/**
 * §3.7 C 端 Dashboard 统计
 * 后端返 { today, thisMonth, total, done, avgAiRate, passRate, dailyTrend[30] }
 * dailyTrend 每项 { date: 'yyyy-MM-dd', count, avgRate }
 */
export function getStatistics() {
  if (MOCK_MODE) {
    // 造 30 天假趋势 + 汇总指标，供离线联调
    const dailyTrend = Array.from({ length: 30 }, (_, i) => {
      const d = new Date(Date.now() - (29 - i) * 24 * 3600 * 1000)
      const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), dd = String(d.getDate()).padStart(2, '0')
      const count = i > 22 ? Math.floor(Math.random() * 4) : Math.floor(Math.random() * 2)
      const avgRate = count ? Math.round((15 + Math.random() * 20) * 10) / 10 : null
      return { date: `${y}-${m}-${dd}`, count, avgRate }
    })
    return Promise.resolve({
      today: 2, thisMonth: 18, total: 47, done: 42,
      avgAiRate: 22.4, passRate: 76.2,
      dailyTrend,
    })
  }
  return http({ url: '/api/v1/detect/statistics' })
}

/**
 * §3.5 取消检测（RUNNING/PENDING 状态可用；后端置 FAILED）
 */
export function cancelTask(id) {
  if (MOCK_MODE) return Promise.resolve()
  return http({ url: `/api/v1/detect/tasks/${id}/cancel`, method: 'POST' })
}

/**
 * §3.6 删除任务（同时删存储原稿）
 */
export function deleteTask(id) {
  if (MOCK_MODE) return Promise.resolve()
  return http({ url: `/api/v1/detect/tasks/${id}`, method: 'DELETE' })
}

/**
 * §8.2 直接文本检测（不生成任务）· Wave 1 · 1.4 文本粘贴
 */
export function detectTextDirect(text) {
  if (MOCK_MODE) {
    const hash = [...text].reduce((s, c) => (s * 31 + c.charCodeAt(0)) >>> 0, 5381)
    const rate = (hash % 10000) / 10000
    const sents = text.split(/(?<=[。！？!?.])/).filter((s) => s.trim()).map((t, i) => ({
      sentenceIdx: i,
      text: t,
      aiProb: ((hash + i * 7919) % 10000) / 10000,
    }))
    return Promise.resolve({
      aiProb: rate,
      calibratedProb: rate,
      riskLevel: rate >= 0.7 ? 'high' : rate >= 0.4 ? 'medium' : 'low',
      warning: '',
      branchScores: { statistical: rate * 0.9, deberta: rate, roberta: Math.min(1, rate * 1.05) },
      sentences: sents,
    })
  }
  return http({
    url: '/api/v1/detect/paragraph',
    method: 'POST',
    data: { text, returnSentences: true },
  }).then((d) => ({
    aiProb: d.ai_prob ?? d.aiProb ?? 0,
    calibratedProb: d.calibrated_prob ?? d.calibratedProb ?? 0,
    riskLevel: d.risk_level ?? d.riskLevel ?? 'low',
    warning: d.warning || '',
    branchScores: d.branch_scores || d.branchScores || {},
    sentences: (d.sentences || []).map((s) => ({
      sentenceIdx: s.sentence_idx ?? s.sentenceIdx,
      text: text.substring(s.offset_start ?? 0, Math.min(s.offset_end ?? text.length, text.length)),
      aiProb: s.ai_prob ?? s.aiProb,
    })),
  }))
}

export function requestHumanize(taskId, paragraphIdx) {
  if (MOCK_MODE) {
    return Promise.resolve(
      '人工智能近年来发展得很快，深度学习也因此被越来越多地用在自然语言处理上。情感分析是其中一个重要方向，学界和产业界都很关注它。'
    )
  }
  return http({
    url: '/api/v1/humanize',
    method: 'POST',
    data: { taskId, paragraphIdx },
  }).then((d) => d.rewrittenText)
}
