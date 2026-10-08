import { defineConfig, devices } from '@playwright/test'

/**
 * 前端 E2E 配置（Playwright）
 *
 * 约定：
 *  - 目标应用 = web/（Vue3 + Vite），dev server 由 webServer 自动拉起在 5173
 *  - 后端接口一律用 page.route 拦截并返回确定性 fixture，E2E 不依赖真实后端/DB/Redis
 *  - 浏览器缓存落到仓库内 .playwright-browsers（沙箱内可写），避免污染系统目录
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'e2e-report', open: 'never' }],
    ['json', { outputFile: 'e2e-report/results.json' }],
  ],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  },
  projects: [
    // 复用本机已安装的 Chrome（channel: 'chrome'），无需下载 Playwright 自带 Chromium
    { name: 'chromium', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
    timeout: 120_000,
  },
})
