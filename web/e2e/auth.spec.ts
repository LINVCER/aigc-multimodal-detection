import { test, expect } from '@playwright/test'
import { mockApi, seedAuth, USER } from './fixtures'

test.describe('登录 / 注册 · 认证', () => {
  test('未登录访问受保护路由 → 重定向到登录页', async ({ page }) => {
    await mockApi(page)
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByText('登录后即可检测报告')).toBeVisible()
  })

  test('登录表单：账号或密码为空时提交按钮禁用', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')

    const submit = page.locator('button.primary')
    await expect(submit).toBeDisabled()

    await page.getByPlaceholder('账号/邮箱').fill('zhangsan')
    await expect(submit).toBeDisabled()

    await page.getByPlaceholder('请输入密码').fill('abc123')
    await expect(submit).toBeEnabled()
  })

  test('登录成功 → 跳转检测记录页并加载列表', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')

    await page.getByPlaceholder('账号/邮箱').fill('zhangsan')
    await page.getByPlaceholder('请输入密码').fill('abc123')
    await page.locator('button.primary').click()

    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByRole('heading', { name: '检测记录' })).toBeVisible()
    await expect(page.getByText('毕业论文-初稿')).toBeVisible()
  })

  test('登录失败 → 展示服务端错误提示', async ({ page }) => {
    await mockApi(page, { loginError: '用户名或密码错误' })
    await page.goto('/login')

    await page.getByPlaceholder('账号/邮箱').fill('zhangsan')
    await page.getByPlaceholder('请输入密码').fill('wrong-pwd')
    await page.locator('button.primary').click()

    await expect(page.locator('.alert')).toContainText('用户名或密码错误')
  })

  test('切换到注册模式 → 出现确认密码与验证码字段', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')

    // 先填充账号：账号框自动聚焦，若为空则 blur 会插入错误文案导致布局位移，
    // 使「立即注册」的 mousedown/mouseup 落在不同元素上而点击落空。
    await page.getByPlaceholder('账号/邮箱').fill('zhangsan')
    await page.locator('.foot-action').click()
    await expect(page).toHaveURL(/mode=register/)
    await expect(page.getByPlaceholder('再次输入密码')).toBeVisible()
    await expect(page.getByPlaceholder('4 位字符，不区分大小写')).toBeVisible()
  })

  test('注册密码规则实时校验', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login?mode=register')

    await page.getByPlaceholder('设置密码').fill('abc')
    await expect(page.locator('.rule', { hasText: '含数字' })).not.toHaveClass(/ok/)

    await page.getByPlaceholder('设置密码').fill('abc123')
    await expect(page.locator('.rule', { hasText: '含数字' })).toHaveClass(/ok/)
    await expect(page.locator('.rule', { hasText: '6-32 位' })).toHaveClass(/ok/)
  })

  test('注册成功 → 自动登录并跳转', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login?mode=register')

    await page.getByPlaceholder('账号/邮箱').fill('newuser')
    await page.getByPlaceholder('设置密码').fill('abc123')
    await page.getByPlaceholder('再次输入密码').fill('abc123')
    await page.getByPlaceholder('4 位字符，不区分大小写').fill('AB12')
    // 勾选框本体 opacity:0 不可见，点击其可见的样式元素 <i>
    await page.locator('.chk', { hasText: '同意' }).locator('i').click()

    await page.locator('button.primary').click()
    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByRole('heading', { name: '检测记录' })).toBeVisible()
  })

  test('登录成功后 token 与用户信息写入 localStorage', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')

    await page.getByPlaceholder('账号/邮箱').fill('zhangsan')
    await page.getByPlaceholder('请输入密码').fill('abc123')
    await page.locator('button.primary').click()
    await expect(page).toHaveURL(/\/dashboard/)

    const token = await page.evaluate(() => localStorage.getItem('access_token'))
    const info = await page.evaluate(() => localStorage.getItem('user_info'))
    expect(token).toBeTruthy()
    expect(JSON.parse(info || '{}').username).toBe(USER.username)
  })

  test('密码可见性切换：默认 password，点击后为 text', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')

    const pwd = page.getByPlaceholder('请输入密码')
    await pwd.fill('abc123')
    await expect(pwd).toHaveAttribute('type', 'password')

    await page.locator('button.eye').click()
    await expect(pwd).toHaveAttribute('type', 'text')
  })
})
