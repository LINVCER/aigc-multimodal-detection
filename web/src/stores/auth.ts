import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, register as apiRegister, logout as apiLogout, me as apiMe, changePassword as apiChangePassword } from '@/api/auth'
import type { UserInfo } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>('')
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)

  function restore() {
    token.value = localStorage.getItem('access_token') || ''
    const raw = localStorage.getItem('user_info')
    if (raw) {
      try { user.value = JSON.parse(raw) } catch { /* ignore */ }
    }
  }

  async function login(username: string, password: string, captchaId?: string, captchaCode?: string) {
    loading.value = true
    try {
      const data = await apiLogin(username, password, captchaId, captchaCode)
      token.value = data.accessToken
      user.value = data.user
      localStorage.setItem('access_token', data.accessToken)
      localStorage.setItem('user_info', JSON.stringify(data.user))
    } finally {
      loading.value = false
    }
  }

  async function register(username: string, password: string, confirmPassword: string, captchaId?: string, captchaCode?: string) {
    loading.value = true
    try {
      const data = await apiRegister(username, password, confirmPassword, captchaId, captchaCode)
      token.value = data.accessToken
      user.value = data.user
      localStorage.setItem('access_token', data.accessToken)
      localStorage.setItem('user_info', JSON.stringify(data.user))
    } finally {
      loading.value = false
    }
  }

  /** 启动时用 /me 校验本地 token 是否仍有效，并刷新角色等信息；失效则清本地态 */
  async function validate(): Promise<boolean> {
    if (!token.value) return false
    try {
      user.value = await apiMe()
      localStorage.setItem('user_info', JSON.stringify(user.value))
      return true
    } catch (e: any) {
      // 网络异常不清 token（离线也能看本地态）；只有服务端明确说无效才清
      if (e?.response?.status === 401 || /token/i.test(e?.message || '')) clearLocal()
      return false
    }
  }

  async function changePassword(oldPassword: string, newPassword: string, confirmPassword: string) {
    loading.value = true
    try { await apiChangePassword(oldPassword, newPassword, confirmPassword) } finally { loading.value = false }
    // 服务端已作废当前 token
    clearLocal()
  }

  function clearLocal() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  async function logout() {
    try { await apiLogout() } catch { /* 后端可能无该接口，忽略 */ }
    clearLocal()
  }

  return { token, user, loading, restore, validate, login, register, changePassword, logout }
})
