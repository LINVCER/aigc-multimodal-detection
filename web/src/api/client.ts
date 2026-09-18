import axios, { AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

// dev 走 vite proxy /api → http://localhost:8080；prod 由部署侧 Nginx 分发
export const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

export const http: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (resp) => {
    // 若依 R 结构 { code, msg, data }；code=200/0 为成功
    const body = resp.data
    if (body && typeof body.code === 'number' && body.code !== 0 && body.code !== 200) {
      ElMessage.error(body.msg ?? '请求失败')
      return Promise.reject(new Error(body.msg ?? 'request failed'))
    }
    return resp
  },
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('access_token')
      // 简单粗暴：跳登录
      if (location.hash !== '#/login') location.hash = '/login'
      return Promise.reject(err)
    }
    ElMessage.error(err.message || '网络异常')
    return Promise.reject(err)
  },
)
