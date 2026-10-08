import { test, expect } from '@playwright/test'
import { mockApi, seedAuth } from './fixtures'

test.describe('检测记录 · Dashboard', () => {
  test('渲染统计卡片、趋势图与任务列表', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/dashboard')

    await expect(page.getByRole('heading', { name: '检测记录' })).toBeVisible()
    await expect(page.locator('.stat-card')).toHaveCount(4)
    await expect(page.locator('.stat-card').first()).toContainText('今日')
    await expect(page.locator('.trend-card')).toBeVisible()

    await expect(page.getByText('毕业论文-初稿')).toBeVisible()
    await expect(page.getByText('开题报告')).toBeVisible()
  })

  test('任务状态映射为中文标签', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/dashboard')

    await expect(page.locator('.el-table')).toContainText('已完成')
    await expect(page.locator('.el-table')).toContainText('检测中')
  })

  test('无任务时展示空状态', async ({ page }) => {
    await mockApi(page, { tasks: [] })
    await seedAuth(page)
    await page.goto('/dashboard')

    await expect(page.getByText('还没有检测记录')).toBeVisible()
    await expect(page.getByText('去上传')).toBeVisible()
  })

  test('点击任务标题进入详情页', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/dashboard')

    await page.locator('.title-link', { hasText: '毕业论文-初稿' }).click()
    await expect(page).toHaveURL(/\/task\/101/)
  })

  test('顶部导航可进入上传页', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/dashboard')

    await page.getByRole('button', { name: '+ 上传论文' }).click()
    await expect(page).toHaveURL(/\/upload/)
  })
})
