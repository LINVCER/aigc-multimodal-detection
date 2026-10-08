<script setup>
import { ref, computed, watch } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'
import { http, MOCK_MODE } from '@/utils/request'

/*
 * 登录 / 注册页
 *   行内校验 · 密码可见切换 · 注册时密码强度与隐私协议勾选 · 记住账号 · 验证码点击刷新
 *   服务端错误（锁定 / 验证码 / 账号停用）显示在表单内；登录后回到来源页（pending_login_redirect）
 */
const auth = useAuth()
const REMEMBER_KEY = 'remember_username'

const mode = ref('login')   // 'login' | 'register'
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPwd = ref(false)
const remember = ref(true)
const agreed = ref(false)
const captchaId = ref('')
const captchaCode = ref('')
const captchaImg = ref('')
const captchaLoading = ref(false)
const captchaFailed = ref(false)
const serverError = ref('')
const touched = ref({})

const USERNAME_RE = /^[A-Za-z0-9_.@-]{2,64}$/
const usernameError = computed(() => {
  if (!touched.value.username) return ''
  if (!username.value.trim()) return '请输入账号'
  if (mode.value === 'register' && !USERNAME_RE.test(username.value.trim())) return '只能包含字母、数字、_ . @ -，2-64 位'
  return ''
})
const passwordError = computed(() => {
  if (!touched.value.password) return ''
  if (!password.value) return '请输入密码'
  if (mode.value === 'register') {
    if (password.value.length < 6 || password.value.length > 32) return '密码长度 6-32 位'
    if (!/[A-Za-z]/.test(password.value) || !/[0-9]/.test(password.value)) return '需同时包含字母和数字'
    if (password.value.toLowerCase() === username.value.trim().toLowerCase()) return '密码不能与账号相同'
  }
  return ''
})
const confirmError = computed(() => {
  if (mode.value !== 'register' || !touched.value.confirm) return ''
  if (!confirmPassword.value) return '请再次输入密码'
  if (confirmPassword.value !== password.value) return '两次输入的密码不一致'
  return ''
})
const captchaError = computed(() => (touched.value.captcha && captchaImg.value && !captchaCode.value.trim() ? '请输入验证码' : ''))

const strength = computed(() => {
  const p = password.value
  if (!p) return 0
  let s = 0
  if (p.length >= 8) s++
  if (p.length >= 12) s++
  if (/[A-Za-z]/.test(p) && /[0-9]/.test(p)) s++
  if (/[^A-Za-z0-9]/.test(p)) s++
  return Math.min(4, s)
})
const STRENGTH_LABEL = ['', '弱', '一般', '较强', '强']

const canSubmit = computed(() => {
  if (auth.loading) return false
  if (!username.value.trim() || !password.value) return false
  if (captchaImg.value && !captchaCode.value.trim()) return false
  if (mode.value === 'register') {
    if (!confirmPassword.value || confirmPassword.value !== password.value) return false
    if (!agreed.value) return false
  }
  return true
})

async function loadCaptcha() {
  if (MOCK_MODE) { captchaId.value = ''; captchaImg.value = ''; return }
  captchaLoading.value = true
  captchaFailed.value = false
  try {
    const data = await http({ url: '/api/v1/auth/captcha', method: 'GET', auth: false, silent: true })
    captchaId.value = data.captchaId
    captchaImg.value = data.imageBase64
  } catch (e) {
    captchaId.value = ''
    captchaImg.value = ''
    captchaFailed.value = true
  } finally {
    captchaLoading.value = false
    captchaCode.value = ''
  }
}

onLoad((q) => {
  if (q && q.mode === 'register') mode.value = 'register'
  const saved = uni.getStorageSync(REMEMBER_KEY)
  if (saved) { username.value = saved; remember.value = true }
  loadCaptcha()
})

watch(mode, () => {
  serverError.value = ''
  touched.value = {}
  confirmPassword.value = ''
  if (!captchaImg.value) loadCaptcha()
})

function afterLogin() {
  if (remember.value) uni.setStorageSync(REMEMBER_KEY, username.value.trim())
  else uni.removeStorageSync(REMEMBER_KEY)
  const back = uni.getStorageSync('pending_login_redirect')
  uni.removeStorageSync('pending_login_redirect')
  if (back && /^\/pages\//.test(back) && !back.startsWith('/pages/login/')) {
    uni.reLaunch({ url: back })
  } else {
    uni.reLaunch({ url: '/pages/home/home' })
  }
}

async function onSubmit() {
  touched.value = { username: true, password: true, confirm: true, captcha: true }
  serverError.value = ''
  if (usernameError.value || passwordError.value || confirmError.value || captchaError.value) return
  if (mode.value === 'register' && !agreed.value) {
    serverError.value = '请先阅读并同意《隐私政策》'
    return
  }
  const u = username.value.trim()
  try {
    if (mode.value === 'register') {
      await auth.register(u, password.value, confirmPassword.value, captchaId.value, captchaCode.value)
      uni.showToast({ title: '注册成功', icon: 'success' })
    } else {
      await auth.login(u, password.value, captchaId.value, captchaCode.value)
    }
    afterLogin()
  } catch (e) {
    serverError.value = e?.message || (mode.value === 'register' ? '注册失败' : '登录失败')
    loadCaptcha()   // 验证码一次性，失败后必须换一张
  }
}

function goPrivacy() { uni.navigateTo({ url: '/pages/about/privacy' }) }

/**
 * 微信一键登录（Wave 3.1）
 * 流程：wx.login → code → POST /api/v1/auth/wechat/login
 */
async function onWechatLogin() {
  uni.login({
    provider: 'weixin',
    success: async (res) => {
      if (!res.code) {
        uni.showToast({ title: '未拿到微信 code', icon: 'none' })
        return
      }
      try {
        await auth.loginByWechat({ code: res.code })
        afterLogin()
      } catch (e) {
        serverError.value = e?.message || '微信登录失败'
      }
    },
    fail: () => uni.showToast({ title: '微信授权失败', icon: 'none' }),
  })
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <image class="logo" src="/static/logo.png" mode="aspectFill" />
      <text class="brand">知源</text>
      <text class="tagline">看得懂的论文 AI 率检测 · 溯源 · 不代写</text>
    </view>

    <view class="form">
      <view class="seg">
        <text class="seg-item" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</text>
        <text class="seg-item" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</text>
      </view>

      <view class="field" :class="{ error: usernameError }">
        <input v-model="username" class="input" placeholder="学号 / 工号 / 邮箱" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.username = true" />
      </view>
      <text v-if="usernameError" class="err">{{ usernameError }}</text>

      <view class="field pwd" :class="{ error: passwordError }">
        <input v-model="password" class="input" :placeholder="mode === 'register' ? '设置密码（6-32 位，含字母和数字）' : '密码'" :password="!showPwd" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.password = true" />
        <text class="eye" @click="showPwd = !showPwd">{{ showPwd ? '隐藏' : '显示' }}</text>
      </view>
      <text v-if="passwordError" class="err">{{ passwordError }}</text>
      <view v-if="mode === 'register' && password" class="strength">
        <view v-for="n in 4" :key="n" class="bar" :class="{ on: n <= strength, ['lv' + strength]: n <= strength }" />
        <text class="strength-text">{{ STRENGTH_LABEL[strength] }}</text>
      </view>

      <template v-if="mode === 'register'">
        <view class="field" :class="{ error: confirmError }">
          <input v-model="confirmPassword" class="input" placeholder="再次输入密码" :password="!showPwd" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.confirm = true" />
        </view>
        <text v-if="confirmError" class="err">{{ confirmError }}</text>
      </template>

      <view v-if="!MOCK_MODE" class="captcha-row">
        <view class="field captcha-field" :class="{ error: captchaError }">
          <input v-model="captchaCode" class="input" placeholder="验证码" maxlength="6" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.captcha = true" />
        </view>
        <view class="captcha-box" hover-class="captcha-box-hover" @click="loadCaptcha">
          <image v-if="captchaImg && !captchaLoading" class="captcha-img" :src="captchaImg" mode="aspectFill" />
          <text v-else class="captcha-hint">{{ captchaLoading ? '加载中…' : captchaFailed ? '点击重试' : '获取验证码' }}</text>
        </view>
      </view>
      <text v-if="captchaError" class="err">{{ captchaError }}</text>
      <text v-else-if="captchaFailed" class="err">验证码服务暂时不可用，点击右侧重试</text>

      <view class="opts">
        <view class="chk" @click="remember = !remember">
          <view class="box" :class="{ on: remember }"><text v-if="remember">✓</text></view>
          <text class="chk-text">记住账号</text>
        </view>
        <view v-if="mode === 'register'" class="chk" @click="agreed = !agreed">
          <view class="box" :class="{ on: agreed }"><text v-if="agreed">✓</text></view>
          <text class="chk-text">同意</text><text class="link" @click.stop="goPrivacy">《隐私政策》</text>
        </view>
        <text v-else class="muted">忘记密码请联系管理员</text>
      </view>

      <view v-if="serverError" class="server-error"><text>{{ serverError }}</text></view>

      <button class="submit" :class="{ disabled: !canSubmit }" :disabled="!canSubmit" :loading="auth.loading" @click="onSubmit">{{ mode === 'login' ? '登 录' : '注册并登录' }}</button>

      <!-- 微信一键登录 · 仅小程序端可见（H5 不支持 uni.login provider=weixin）-->
      <!-- #ifdef MP-WEIXIN -->
      <view class="divider"><text class="divider-text">或</text></view>
      <button class="wechat-btn" @click="onWechatLogin">
        <view class="wechat-icon" />
        <text class="wechat-text">微信一键登录</text>
      </button>
      <!-- #endif -->

      <text class="footer-hint">{{ mode === 'login' ? '还没有账号？' : '已有账号？' }}<text class="switch-link" @click="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? '立即注册' : '去登录' }}</text></text>
      <text class="foot-note">课题阶段免费 · 不代写、不改写 · 结果仅供参考</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: $bg-primary;
  padding: #{"calc(140rpx + env(safe-area-inset-top))"} $sp-8 60rpx;
}

/* Hero */
.hero { margin-bottom: 72rpx; }
.logo { width: 96rpx; height: 96rpx; border-radius: 24rpx; margin-bottom: $sp-4; }
.brand {
  display: block;
  font-size: $fs-large-title;
  font-weight: $fw-bold;
  letter-spacing: $tracking-tight;
  color: $label-primary;
  line-height: $lh-tight;
}
.tagline { display: block; font-size: $fs-subhead; color: $label-secondary; margin-top: $sp-2; }

/* 分段 */
.seg { display: flex; background: $bg-grouped-primary; border-radius: $radius-card; padding: 4rpx; margin-bottom: $sp-4; }
.seg-item {
  flex: 1; text-align: center; padding: 12rpx 0;
  font-size: $fs-subhead; color: $label-secondary; border-radius: 12rpx;
  &.active { background: $bg-primary; color: $label-primary; font-weight: $fw-semibold; box-shadow: $shadow-card; }
}

/* 输入框 */
.field {
  background: $bg-grouped-primary;
  border-radius: $radius-card;
  padding: 4rpx $sp-4;
  margin-bottom: $sp-3;
  border: $stroke-hairline solid transparent;
  &.error { border-color: $danger-solid; }
  &.pwd { display: flex; align-items: center; }
}
.input { flex: 1; height: $size-input-h; font-size: $fs-body; color: $label-primary; min-width: 0; }
.eye { flex: none; font-size: $fs-footnote; color: $brand-primary; padding-left: $sp-2; }
.err { display: block; margin: -8rpx 0 $sp-3 $sp-2; font-size: $fs-caption-1; color: $danger-fg; }

.strength { display: flex; align-items: center; gap: 8rpx; margin: -4rpx 0 $sp-3 $sp-1; }
.bar { width: 64rpx; height: 8rpx; border-radius: 4rpx; background: $fill-tertiary; }
.bar.on.lv1 { background: $danger-solid; } .bar.on.lv2 { background: $warning-solid; } .bar.on.lv3 { background: $info-fg; } .bar.on.lv4 { background: $success-solid; }
.strength-text { font-size: $fs-caption-1; color: $label-secondary; margin-left: $sp-2; }

.captcha-row { display: flex; align-items: flex-start; gap: $sp-2; }
.captcha-field { flex: 1; }
.captcha-box {
  flex: none; width: 200rpx; height: $size-input-h;
  border-radius: $radius-card; border: $stroke-hairline solid $separator;
  display: flex; align-items: center; justify-content: center; overflow: hidden;
  background: $bg-primary;
}
.captcha-box-hover { opacity: 0.7; }
.captcha-img { width: 100%; height: 100%; }
.captcha-hint { font-size: $fs-caption-1; color: $brand-primary; }

.opts { display: flex; justify-content: space-between; align-items: center; margin: $sp-1 $sp-1 0; flex-wrap: wrap; gap: $sp-2; }
.chk { display: flex; align-items: center; gap: 10rpx; }
.box {
  width: 34rpx; height: 34rpx; border-radius: 8rpx; border: 2rpx solid $label-tertiary;
  display: flex; align-items: center; justify-content: center;
  &.on { background: $brand-primary; border-color: $brand-primary; }
  text { color: #fff; font-size: 22rpx; line-height: 1; }
}
.chk-text { font-size: $fs-footnote; color: $label-secondary; }
.link { font-size: $fs-footnote; color: $brand-primary; }
.muted { font-size: $fs-caption-1; color: $label-tertiary; }

.server-error {
  margin-top: $sp-3; padding: $sp-2 $sp-3; border-radius: $radius-md;
  background: $danger-bg;
  text { font-size: $fs-footnote; color: $danger-fg; line-height: $lh-normal; }
}

/* 主按钮 */
.submit {
  margin-top: $sp-5;
  height: $size-btn-h-lg;
  line-height: $size-btn-h-lg;
  background: $brand-primary;
  color: #FFFFFF;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  border-radius: $radius-pill;
  letter-spacing: 2rpx;
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;
  &:active { transform: scale(#{$tap-scale}); opacity: 0.88; }
  &.disabled { opacity: 0.45; }
}

.divider {
  display: flex; align-items: center; justify-content: center;
  margin: $sp-5 0 $sp-3;
  &::before, &::after { content: ''; flex: 1; height: $stroke-hairline; background: $separator; }
}
.divider-text { padding: 0 $sp-3; font-size: $fs-caption-1; color: $label-secondary; }

.wechat-btn {
  height: $size-btn-h-lg; line-height: $size-btn-h-lg;
  background: #07C160; color: #FFFFFF;
  font-size: $fs-headline; font-weight: $fw-semibold; border-radius: $radius-pill;
  display: flex; align-items: center; justify-content: center; gap: $sp-2;
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;
  &:active { transform: scale(#{$tap-scale}); opacity: 0.88; }
}
.wechat-icon {
  width: 40rpx; height: 40rpx;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23FFFFFF'><path d='M9.5 4C5.4 4 2 6.6 2 10c0 1.8 1 3.5 2.6 4.6L4 17l2.7-1.4c.9.2 1.8.3 2.8.3.3 0 .6 0 .9-.1-.2-.6-.4-1.3-.4-2 0-3.3 3.3-6 7.5-6 .3 0 .6 0 .9.1C17.7 5.6 13.9 4 9.5 4zm-3 3.6c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm5.5 0c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1z'/><path d='M22 14c0-2.8-2.9-5-6.5-5S9 11.2 9 14s2.9 5 6.5 5c.8 0 1.6-.1 2.3-.3l2 1-.5-2C21 16.7 22 15.4 22 14zm-9-1.4c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.4-.8.8-.8zm4.5 0c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.3-.8.8-.8z'/></svg>") no-repeat center / contain;
}

.footer-hint { display: block; margin-top: $sp-6; font-size: $fs-caption-1; color: $label-secondary; text-align: center; line-height: $lh-normal; }
.switch-link { color: $brand-primary; }
.foot-note { display: block; margin-top: $sp-3; font-size: $fs-caption-2; color: $label-tertiary; text-align: center; }
</style>
