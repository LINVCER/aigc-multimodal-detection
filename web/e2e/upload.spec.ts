import { test, expect } from '@playwright/test'
import { mockApi, seedAuth } from './fixtures'

test.describe('论文检测 · 上传 / 粘贴', () => {
  test('默认进入上传模式，展示场景选择与投放区', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/upload')

    await expect(page.getByRole('heading', { name: '论文检测' })).toBeVisible()
    await expect(page.locator('.sc')).toHaveCount(6)
    await expect(page.getByText('拖入论文')).toBeVisible()
    await expect(page.locator('button.cta')).toBeDisabled()
  })

  test('选择场景后红线随之变化', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/upload')

    await page.locator('.sc', { hasText: '学术·博士' }).click()
    await expect(page.locator('.sc.active')).toContainText('学术·博士')
    await expect(page.locator('.group-hint')).toContainText('≤ 10%')
  })

  test('选择文件后可提交，提交后跳转任务详情', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/upload')

    await page.setInputFiles('input[type=file]', {
      name: 'paper.txt', mimeType: 'text/plain', buffer: Buffer.from('这是一篇测试论文的正文内容。'),
    })

    await expect(page.locator('.picked-name')).toHaveText('paper.txt')
    const cta = page.locator('button.cta')
    await expect(cta).toBeEnabled()
    await cta.click()

    await expect(page).toHaveURL(/\/task\/999/)
  })

  test('拒绝不支持的文件类型', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/upload')

    await page.setInputFiles('input[type=file]', {
      name: 'photo.png', mimeType: 'image/png', buffer: Buffer.from('fake'),
    })

    await expect(page.locator('.el-message')).toContainText('只支持 PDF / Word / TXT')
    await expect(page.locator('.picked')).toHaveCount(0)
  })

  test('粘贴模式：即时检测并展示校准概率与结论', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/upload?mode=paste')

    await page.locator('textarea').fill('这是一段用于即时检测的示例文本，长度超过一百二十字以便触发可靠性判定，内容仅用于端到端测试。'.repeat(3))
    await page.getByRole('button', { name: '即时检测' }).click()

    await expect(page.locator('.result-verdict')).toContainText('更像人写')
    await expect(page.locator('.result-rate')).toContainText('25.0')
  })

  test('粘贴不足 120 字时给出可靠性提示', async ({ page }) => {
    await mockApi(page)
    await seedAuth(page)
    await page.goto('/upload?mode=paste')

    await page.locator('textarea').fill('太短了')
    await expect(page.locator('.paste-warn')).toContainText('不足 120 字')
  })
})
