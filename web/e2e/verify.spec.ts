import { test, expect } from '@playwright/test'
import { mockApi } from './fixtures'

test.describe('报告真伪验证 · 公开页', () => {
  test('未登录也可访问验证页', async ({ page }) => {
    await mockApi(page)
    await page.goto('/verify')

    await expect(page.getByRole('heading', { name: '验证检测报告' })).toBeVisible()
    await expect(page).toHaveURL(/\/verify/)
  })

  test('缺少编号或验证码 → 前端拦截并提示', async ({ page }) => {
    await mockApi(page)
    await page.goto('/verify')

    await page.getByRole('button', { name: /验\s*证/ }).click()
    await expect(page.locator('.err')).toContainText('请输入报告编号和验证码')
  })

  test('输入编号与验证码 → 展示验证通过结果', async ({ page }) => {
    await mockApi(page)
    await page.goto('/verify')

    await page.getByPlaceholder('ZY-20261008-XXXXXX').fill('zy-20261008-abc123')
    await page.getByPlaceholder('PDF 封面 8 位验证码').fill('abcd1234')
    await page.getByRole('button', { name: /验\s*证/ }).click()

    await expect(page.locator('.result-title')).toContainText('报告真实有效')
    await expect(page.locator('.kv')).toContainText('ZY-20261008-ABC123')
  })

  test('URL 带编号与 code 时自动验证', async ({ page }) => {
    await mockApi(page)
    await page.goto('/verify/ZY-20261008-ABC123?code=ABCD1234')

    await expect(page.locator('.result-title')).toContainText('报告真实有效')
  })
})
