import { defineStore } from 'pinia'
import { http, MOCK_MODE } from '@/utils/request'

export const useAuth = defineStore('auth', {
  state: () => ({
    token: '',
    username: '',
    loading: false,
  }),

  actions: {
    /**
     * 从本地存储恢复登录态（App onLaunch 调用）
     */
    restore() {
      this.token = uni.getStorageSync('access_token') || ''
      this.username = uni.getStorageSync('username') || ''
    },

    /**
     * 登录
     * @param {string} username 学号 / 工号
     * @param {string} password 密码
     */
    async login(username, password) {
      this.loading = true
      try {
        let token
        if (MOCK_MODE) {
          token = 'mock-token'
        } else {
          const data = await http({
            url: '/api/v1/auth/login',
            method: 'POST',
            data: { username, password },
            auth: false,
          })
          token = data.accessToken
        }
        uni.setStorageSync('access_token', token)
        uni.setStorageSync('username', username)
        this.token = token
        this.username = username
      } finally {
        this.loading = false
      }
    },

    /**
     * 退出登录
     */
    logout() {
      uni.removeStorageSync('access_token')
      uni.removeStorageSync('username')
      this.token = ''
      this.username = ''
      uni.reLaunch({ url: '/pages/login/login' })
    },
  },
})
