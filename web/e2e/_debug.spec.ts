import { test } from '@playwright/test'
import { mockApi } from './fixtures'

test('debug foot-action 2', async ({ page }) => {
  page.on('pageerror', (e) => console.log('[pageerror]', e.message))
  await mockApi(page)
  await page.goto('/login')

  const el = page.locator('.foot-action')
  console.log('box=', JSON.stringify(await el.first().boundingBox()))
  console.log('tag=', await el.first().evaluate((n) => (n as HTMLElement).tagName + ' href=' + (n as HTMLAnchorElement).getAttribute('href')))

  await el.first().dispatchEvent('click')
  await page.waitForTimeout(500)
  console.log('after dispatch url=', page.url())

  await page.getByText('立即注册').click({ force: true })
  await page.waitForTimeout(500)
  console.log('after force url=', page.url())
  console.log('card=', (await page.locator('.card').innerText()).replace(/\n/g, '|').slice(0, 100))
})
