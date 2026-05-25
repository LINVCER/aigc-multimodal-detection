import axios from "axios"
import router from "@/router"

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 120000,
  headers: { "Content-Type": "application/json" },
})

// 请求拦截：自动附加 Token + FormData 时清除硬编码 Content-Type
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (config.data instanceof FormData) {
    delete config.headers["Content-Type"]
  }
  return config
})

// Token 刷新状态
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: any) => void
}> = []

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

// 响应拦截：401 自动刷新 Token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/login") &&
      !originalRequest.url?.includes("/auth/register") &&
      !originalRequest.url?.includes("/auth/refresh")
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = localStorage.getItem("refresh_token")
      if (!refreshToken) {
        isRefreshing = false
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        router.push("/login")
        return Promise.reject(error)
      }

      try {
        const { data } = await axios.post(
          "/api/v1/auth/refresh",
          null,
          { params: { refresh_token: refreshToken } }
        )
        localStorage.setItem("access_token", data.access_token)
        localStorage.setItem("refresh_token", data.refresh_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        processQueue(null, data.access_token)
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        localStorage.removeItem("access_token")
        localStorage.removeItem("refresh_token")
        router.push("/login")
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default api
