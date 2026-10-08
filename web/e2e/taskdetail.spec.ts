import { test, expect } from '@playwright/test'
import { mockApi, seedAuth } from './fixtures'

test.describe('检测报告详情', () => {
  test('渲染整体 AI 率、红线与论文标题', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/task/101')

    await expect(page.locator('.ring-rate')).toContainText('12.5')
    await expect(page.locator('.ring-cap')).toContainText('红线 15%')
    await expect(page.locator('.hero-paper')).toContainText('毕业论文-初稿')
  })

  test('段落列表区分正文与非正文（参考文献被排除）', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/task/101')

    await expect(page.locator('.para')).toHaveCount(2)
    await expect(page.locator('.excluded-badge')).toContainText('参考文献')
  })

  test('报告详情页含下载 / 问助手等关键动作', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/task/101')

    await expect(page.getByRole('button', { name: /下载|报告/ }).first()).toBeVisible()
  })
})
