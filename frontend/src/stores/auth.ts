import { defineStore } from "pinia"
import { ref } from "vue"
import api from "@/api"

export const useAuthStore = defineStore("auth", () => {
  const user = ref<any>(null)
  const isLoggedIn = ref(!!localStorage.getItem("access_token"))

  async function login(username: string, password: string) {
    const { data } = await api.post("/auth/login", { username, password })
    localStorage.setItem("access_token", data.access_token)
    localStorage.setItem("refresh_token", data.refresh_token)
    isLoggedIn.value = true
    await fetchUser()
  }

  async function register(form: { username: string; email: string; password: string; role: string }) {
    await api.post("/auth/register", form)
  }

  async function fetchUser() {
    try {
      const { data } = await api.get("/auth/me")
      user.value = data
      if (data?.role) {
        localStorage.setItem("user_role", data.role)
      }
    } catch {
      isLoggedIn.value = false
      localStorage.removeItem("access_token")
    }
  }

  function logout() {
    // 清理当前用户的检测缓存
    if (user.value?.id || user.value?.username) {
      const userId = user.value?.id || user.value?.username
      localStorage.removeItem(`detection_cache_${userId}`)
    }

    // 清理认证相关数据
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
    localStorage.removeItem("user_role")
    user.value = null
    isLoggedIn.value = false
    window.location.href = "/login"
  }

  async function checkin() {
    const { data } = await api.post("/auth/checkin")
    if (user.value) {
      user.value.quota_remaining = data.quota_remaining
      user.value.last_checkin_date = new Date().toISOString().slice(0, 10)
      user.value.checkin_streak = data.streak
    }
    return data
  }

  async function donate() {
    const { data } = await api.post("/auth/donate")
    if (user.value) {
      user.value.quota_remaining = data.quota_remaining
    }
    return data
  }

  return { user, isLoggedIn, login, register, fetchUser, logout, checkin, donate }
})
