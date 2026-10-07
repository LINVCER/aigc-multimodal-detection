import { defineStore } from 'pinia'
import { http, MOCK_MODE } from '@/utils/request'

export const useAuth = defineStore('auth', {
  state: () => ({
    token: '',
    username: '',
    userId: '',       // 后端 mock login 返回 user.id；W3.c 接入 Sa-Token 后从 /me 拉
    role: '',         // USER / OPS_ADMIN
    loading: false,
  }),

  actions: {
    /** 从本地存储恢复登录态（App onLaunch 调用） */
    restore() {
      this.token = uni.getStorageSync('access_token') || ''
      this.username = uni.getStorageSync('username') || ''
      this.userId = uni.getStorageSync('user_id') || ''
      this.role = uni.getStorageSync('user_role') || ''
    },

    /** 统一落库登录态 */
    _applyLogin(token, user, fallbackName) {
      uni.setStorageSync('access_token', token)
      uni.setStorageSync('username', user.username || fallbackName)
      uni.setStorageSync('user_id', user.id || '')
      uni.setStorageSync('user_role', user.role || '')
      this.token = token
      this.username = user.username || fallbackName
      this.userId = user.id || ''
      this.role = user.role || ''
    },

    /**
     * 登录
     * @param {string} username
     * @param {string} password
     * @param {string} [captchaId]
     * @param {string} [captchaCode]
     */
    async login(username, password, captchaId, captchaCode) {
      this.loading = true
      try {
        let token = 'mock-token'
        let user = { id: '', username, role: 'USER' }
        if (!MOCK_MODE) {
          const payload = { username, password, clientId: 'e5cd7e4891bf95d1d19206ce24a7b32e', grantType: 'password' }
          if (captchaId) { payload.captchaId = captchaId; payload.captchaCode = captchaCode }
          const data = await http({ url: '/api/v1/auth/login', method: 'POST', data: payload, auth: false })
          token = data.accessToken
          user = data.user || user
        }
        this._applyLogin(token, user, username)
      } finally {
        this.loading = false
      }
    },

    /**
     * 注册（注册即登录）
     */
    async register(username, password, confirmPassword, captchaId, captchaCode) {
      this.loading = true
      try {
        let token = 'mock-token'
        let user = { id: '', username, role: 'USER' }
        if (!MOCK_MODE) {
          const payload = { username, password, confirmPassword }
          if (captchaId) { payload.captchaId = captchaId; payload.captchaCode = captchaCode }
          const data = await http({ url: '/api/v1/auth/register', method: 'POST', data: payload, auth: false })
          token = data.accessToken
          user = data.user || user
        }
        this._applyLogin(token, user, username)
      } finally {
        this.loading = false
      }
    },

    /**
     * 微信一键登录（Wave 3.1 · 小程序端）
     * 流程：wx.login 拿 code → POST /api/v1/auth/wechat/login → 存 token
     * @param {{code:string, nickname?:string, avatarUrl?:string}} payload
     */
    async loginByWechat(payload) {
      this.loading = true
      try {
        let token = 'mock-wechat-token'
        let user = { id: '', username: payload.nickname || 'wx-user', role: 'USER' }
        if (!MOCK_MODE) {
          const data = await http({
            url: '/api/v1/auth/wechat/login',
            method: 'POST',
            data: payload,
            auth: false,
          })
          token = data.accessToken
          user = data.user || user
        }
        uni.setStorageSync('access_token', token)
        uni.setStorageSync('username', user.username || 'wx-user')
        uni.setStorageSync('user_id', user.id || '')
        uni.setStorageSync('user_role', user.role || '')
        this.token = token
        this.username = user.username || 'wx-user'
        this.userId = user.id || ''
        this.role = user.role || ''
      } finally {
        this.loading = false
      }
    },

    /** 退出登录 */
    logout() {
      uni.removeStorageSync('access_token')
      uni.removeStorageSync('username')
      uni.removeStorageSync('user_id')
      uni.removeStorageSync('user_role')
      this.token = ''
      this.username = ''
      this.userId = ''
      this.role = ''
      uni.reLaunch({ url: '/pages/login/login' })
    },
  },
})
