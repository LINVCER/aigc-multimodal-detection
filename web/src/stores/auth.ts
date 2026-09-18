import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, logout as apiLogout } from '@/api/auth'
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

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const data = await apiLogin(username, password)
      token.value = data.accessToken
      user.value = data.user
      localStorage.setItem('access_token', data.accessToken)
      localStorage.setItem('user_info', JSON.stringify(data.user))
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    try { await apiLogout() } catch { /* 后端可能无该接口，忽略 */ }
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
  }

  return { token, user, loading, restore, login, logout }
})
