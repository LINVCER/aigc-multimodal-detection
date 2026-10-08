import type { Page } from '@playwright/test'

/**
 * E2E 共享夹具
 *
 * 设计原则：E2E 不依赖真实后端 / DB / Redis。
 * 所有 /api/v1/** 请求在浏览器侧被 page.route 拦截，返回确定性 fixture，
 * 因此用例只验证「前端渲染 + 交互 + 路由」是否正确，与后端实现解耦。
 */

/* ---------------- 常量 ---------------- */

export const TOKEN = 'e2e-token-0001'

export const USER = {
  id: 7,
  username: 'zhangsan',
  realName: '张三',
  role: 'USER',
  orgId: 1,
  orgName: '示例大学',
}

export const OPS_USER = { ...USER, id: 1, username: 'admin', realName: '管理员', role: 'OPS_ADMIN' }

const TINY_PNG =
  'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='

/** 与后端 R 结构一致：{ code, msg, data }，code=200 视为成功 */
function ok(data: unknown) {
  return { code: 200, msg: 'ok', data }
}

/* ---------------- 数据 fixture ---------------- */

export const SAMPLE_TASKS = [
  {
    id: 101, paperTitle: '毕业论文-初稿', status: 'DONE', aiRate: 12.5,
    scenario: 'academic_master', threshold: 15, createdAt: '2026-10-07 10:00',
  },
  {
    id: 102, paperTitle: '开题报告', status: 'RUNNING', aiRate: null,
    scenario: 'academic_bachelor', threshold: 20, createdAt: '2026-10-08 09:00',
  },
]

export const SAMPLE_STATS = {
  today: 3, thisMonth: 12, total: 40, done: 35, avgAiRate: 21.4, passRate: 62.5,
  dailyTrend: Array.from({ length: 30 }, (_, i) => ({
    date: `2026-09-${String(i + 1).padStart(2, '0')}`,
    count: (i % 5) + 1,
    avgRate: i % 3 === 0 ? null : 15 + (i % 20),
  })),
}

export const SAMPLE_DETAIL = {
  id: 101, paperTitle: '毕业论文-初稿', status: 'DONE', aiRate: 12.5,
  scenario: 'academic_master', threshold: 15,
  createdAt: '2026-10-07 10:00', finishedAt: '2026-10-07 10:02', modelVersion: 'v1.2.0',
  reportNo: 'ZY-20261007-ABC123', verifyCode: 'ABCD1234', reportFingerprint: 'fp-abc123',
  verifyUrl: '/verify/ZY-20261007-ABC123?code=ABCD1234', signedAt: '2026-10-07 10:02', verifyCount: 3,
  sourceLabels: { human: 0.7, gpt: 0.2, deepseek: 0.1 },
  paragraphs: [
    {
      paragraphIdx: 0, text: '本段为论文正文内容，用于验证段落级渲染与句子高亮是否正常。',
      aiProb: 0.15, calibratedProb: 0.12, sourceLabel: 'human',
      sentences: [{ sentenceIdx: 0, text: '本段为论文正文内容。', aiProb: 0.15 }], excluded: false,
    },
    {
      paragraphIdx: 1, text: '[1] 张三. 论文题名[J]. 期刊, 2025.',
      aiProb: null, calibratedProb: null, sourceLabel: null,
      sentences: [], excluded: true, excludeReason: 'reference',
    },
  ],
}

export const DIRECT_DETECT = {
  ai_prob: 0.28,
  calibrated_prob: 0.25,
  risk_level: 'low',
  branch_scores: { gpt: 0.2, human: 0.8 },
  sentences: [],
}

export const VERIFY_OK = {
  valid: true, signatureValid: true, message: '报告由知源签发，内容未被改动',
  reportNo: 'ZY-20261008-ABC123', paperTitle: '毕业论文-初稿', scenario: 'academic_master',
  threshold: 15, aiRate: 12.5, pass: true, modelVersion: 'v1.2.0', wordCount: 12000,
  bodyParagraphCount: 42, detectedAt: '2026-10-08T10:00:00+08:00', signedAt: '2026-10-08T10:02:00+08:00',
  fingerprint: 'fp-abc123', verifyCount: 3,
}

/* ---------------- 拦截器 ---------------- */

export interface MockOptions {
  tasks?: unknown[]
  stats?: unknown
  detail?: unknown
  me?: typeof USER
  /** 非空则 /auth/login 返回业务错误 */
  loginError?: string
  /** 非空则 /auth/register 返回业务错误 */
  registerError?: string
}

/**
 * 注册所有 API 路由 mock。未显式覆盖的接口返回 200 + null。
 * 必须在 page.goto 之前调用。
 */
export async function mockApi(page: Page, opts: MockOptions = {}): Promise<void> {
  const tasks = opts.tasks ?? SAMPLE_TASKS
  const me = opts.me ?? USER

  await page.route('**/api/v1/**', async (route) => {
    const req = route.request()
    const path = new URL(req.url()).pathname
    const method = req.method()
    const json = (body: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

    /* ---- 认证 ---- */
    if (path.endsWith('/auth/me')) return json(ok(me))
    if (path.endsWith('/auth/login')) {
      if (opts.loginError) return json({ code: 500, msg: opts.loginError, data: null })
      return json(ok({ accessToken: TOKEN, refreshToken: 'refresh', expiresIn: 3600, user: me }))
    }
    if (path.endsWith('/auth/register')) {
      if (opts.registerError) return json({ code: 500, msg: opts.registerError, data: null })
      return json(ok({ accessToken: TOKEN, refreshToken: 'refresh', expiresIn: 3600, user: me }))
    }
    if (path.endsWith('/auth/username-available')) return json(ok({ available: true }))
    if (path.endsWith('/auth/captcha')) return json(ok({ captchaId: 'cap-1', imageBase64: TINY_PNG }))
    if (path.endsWith('/auth/logout') || path.endsWith('/auth/password')) return json(ok(null))

    /* ---- 检测 ---- */
    if (path.endsWith('/detect/statistics')) return json(ok(opts.stats ?? SAMPLE_STATS))
    if (path.endsWith('/detect/paragraph')) return json(ok(DIRECT_DETECT))
    if (path.endsWith('/detect/submit')) {
      return json(ok({ taskId: 999, paperTitle: '新论文', status: 'PENDING', createdAt: '2026-10-08 12:00' }))
    }
    if (path.endsWith('/detect/tasks') && method === 'GET') {
      return json(ok({ total: tasks.length, rows: tasks }))
    }
    if (/\/detect\/tasks\/\d+$/.test(path) && method === 'GET') {
      return json(ok(opts.detail ?? SAMPLE_DETAIL))
    }
    if (/\/detect\/tasks\/\d+\/(retry|cancel)$/.test(path)) return json(ok(opts.detail ?? SAMPLE_DETAIL))
    if (/\/detect\/tasks\/\d+$/.test(path) && method === 'DELETE') return json(ok(null))

    /* ---- 报告 / 验证 ---- */
    if (path.endsWith('/verify')) return json(ok(VERIFY_OK))
    if (/\/detect\/tasks\/\d+\/compare$/.test(path)) return json(ok(null))

    return json(ok(null))
  })
}

/** 预置登录态：在页面加载前写入 localStorage，跳过登录流程 */
export async function seedAuth(page: Page, user = USER, token = TOKEN): Promise<void> {
  await page.addInitScript(
    ([t, u]) => {
      localStorage.setItem('access_token', t)
      localStorage.setItem('user_info', JSON.stringify(u))
    },
    [token, user] as const,
  )
}
