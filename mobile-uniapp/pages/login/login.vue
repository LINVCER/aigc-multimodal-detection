<script setup>
import { ref, computed, watch } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'
import { http, MOCK_MODE } from '@/utils/request'

/*
 * 登录 / 注册页
 *   逻辑：已登录直跳 · 验证码 5 分钟过期禁提交 · 失败换图 · 锁定倒计时 · 注册用户名查重 · 规则逐条勾选 · 来源页回跳只接受 /pages/ 路径 · 防重复提交
 *   视觉：近白画布 + 极淡色晕 + 毛玻璃白卡 + 单色 accent（system-blue）
 */
const auth = useAuth()
const REMEMBER_KEY = 'remember_username'
const CAPTCHA_TTL_MS = 5 * 60 * 1000
const USERNAME_RE = /^[A-Za-z0-9_.@-]{2,64}$/

const mode = ref('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPwd = ref(false)
const remember = ref(true)
const agreed = ref(false)
const touched = ref({})
const submitting = ref(false)
const serverError = ref('')
const focusField = ref('')

function onFocus(f) { focusField.value = f }
function onBlur(f) { touched.value[f] = true; focusField.value = '' }

/* 验证码 */
const captchaId = ref('')
const captchaImg = ref('')
const captchaCode = ref('')
const captchaLoading = ref(false)
const captchaFailed = ref(false)
const captchaExpired = ref(false)
let captchaTimer = null
const captchaReady = computed(() => MOCK_MODE || (!!captchaId.value && !captchaExpired.value && !captchaLoading.value))

async function loadCaptcha() {
  if (MOCK_MODE) return
  if (captchaTimer) { clearTimeout(captchaTimer); captchaTimer = null }
  captchaLoading.value = true
  captchaFailed.value = false
  captchaExpired.value = false
  captchaCode.value = ''
  try {
    const data = await http({ url: '/api/v1/auth/captcha', method: 'GET', auth: false, silent: true })
    captchaId.value = data.captchaId
    captchaImg.value = data.imageBase64
    captchaTimer = setTimeout(() => { captchaExpired.value = true }, CAPTCHA_TTL_MS)
  } catch (e) {
    captchaId.value = ''
    captchaImg.value = ''
    captchaFailed.value = true
  } finally {
    captchaLoading.value = false
  }
}

/* 锁定倒计时 */
const lockUntil = ref(0)
const now = ref(Date.now())
let tick = null
const lockLeft = computed(() => Math.max(0, Math.ceil((lockUntil.value - now.value) / 1000)))
const lockText = computed(() => {
  const s = lockLeft.value
  if (s <= 0) return ''
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  return `${m}:${String(s % 60).padStart(2, '0')}`
})
function applyLockFromMessage(msg) {
  const m = msg.match(/(\d+)\s*分钟/)
  if (m && /锁定|次数过多/.test(msg)) lockUntil.value = Date.now() + Number(m[1]) * 60 * 1000
}

/* 注册用户名查重 */
const usernameTaken = ref(null)
const checkingName = ref(false)
let nameTimer = null
watch([username, mode], ([u, m]) => {
  usernameTaken.value = null
  if (nameTimer) clearTimeout(nameTimer)
  const v = u.trim()
  if (MOCK_MODE || m !== 'register' || !USERNAME_RE.test(v)) return
  nameTimer = setTimeout(async () => {
    checkingName.value = true
    try {
      const r = await http({ url: '/api/v1/auth/username-available', method: 'GET', data: { username: v }, auth: false, silent: true })
      usernameTaken.value = r && r.available === false
    } catch (e) { usernameTaken.value = null } finally { checkingName.value = false }
  }, 400)
})

/* 校验 */
const usernameError = computed(() => {
  if (!touched.value.username) return ''
  const v = username.value.trim()
  if (!v) return '请输入账号'
  if (mode.value === 'register') {
    if (!USERNAME_RE.test(v)) return '只能包含字母、数字、_ . @ -，2-64 位'
    if (usernameTaken.value) return '该用户名已被注册'
  }
  return ''
})
const pwdRules = computed(() => {
  const p = password.value
  return [
    { ok: p.length >= 6 && p.length <= 32, t: '6-32 位' },
    { ok: /[A-Za-z]/.test(p), t: '含字母' },
    { ok: /[0-9]/.test(p), t: '含数字' },
    { ok: !!p && p.toLowerCase() !== username.value.trim().toLowerCase(), t: '不同于账号' },
  ]
})
const pwdRulesOk = computed(() => pwdRules.value.every((r) => r.ok))
const passwordError = computed(() => {
  if (!touched.value.password) return ''
  if (!password.value) return '请输入密码'
  if (mode.value === 'register' && !pwdRulesOk.value) return '密码不满足规则'
  return ''
})
const confirmError = computed(() => {
  if (mode.value !== 'register' || !touched.value.confirm) return ''
  if (!confirmPassword.value) return '请再次输入密码'
  if (confirmPassword.value !== password.value) return '两次输入的密码不一致'
  return ''
})
const captchaError = computed(() => {
  if (MOCK_MODE || mode.value !== 'register' || !touched.value.captcha) return ''
  if (!captchaReady.value) return captchaExpired.value ? '验证码已过期，点击图片刷新' : '验证码未加载，点击右侧获取'
  if (!captchaCode.value.trim()) return '请输入验证码'
  return ''
})
const formValid = computed(() => {
  if (!username.value.trim() || !password.value) return false
  if (mode.value === 'register' && !MOCK_MODE && (!captchaReady.value || !captchaCode.value.trim())) return false
  if (mode.value === 'register') {
    if (!USERNAME_RE.test(username.value.trim()) || usernameTaken.value) return false
    if (!pwdRulesOk.value || confirmPassword.value !== password.value || !agreed.value) return false
  }
  return true
})
const canSubmit = computed(() => formValid.value && !submitting.value && lockLeft.value === 0)

/* 生命周期 */
function safeRedirect() {
  const back = uni.getStorageSync('pending_login_redirect')
  uni.removeStorageSync('pending_login_redirect')
  return back && /^\/pages\/[A-Za-z0-9_/-]+(\?.*)?$/.test(back) && !back.startsWith('/pages/login/') ? back : ''
}
onLoad((q) => {
  if (auth.token) {
    const back = safeRedirect()
    uni.reLaunch({ url: back || '/pages/home/home' })
    return
  }
  if (q && q.mode === 'register') mode.value = 'register'
  const saved = uni.getStorageSync(REMEMBER_KEY)
  if (saved) { username.value = saved; remember.value = true }
  tick = setInterval(() => { now.value = Date.now() }, 1000)
  if (mode.value === 'register') loadCaptcha()
})
onUnload(() => {
  if (tick) clearInterval(tick)
  if (captchaTimer) clearTimeout(captchaTimer)
  if (nameTimer) clearTimeout(nameTimer)
})
watch(mode, () => {
  serverError.value = ''
  touched.value = {}
  confirmPassword.value = ''
  if (mode.value === 'register' && !captchaReady.value) loadCaptcha()
})

function afterLogin() {
  if (remember.value) uni.setStorageSync(REMEMBER_KEY, username.value.trim())
  else uni.removeStorageSync(REMEMBER_KEY)
  const back = safeRedirect()
  uni.reLaunch({ url: back || '/pages/home/home' })
}

async function onSubmit() {
  if (submitting.value) return
  touched.value = { username: true, password: true, confirm: true, captcha: true }
  serverError.value = ''
  if (lockLeft.value > 0) return
  if (usernameError.value || passwordError.value || confirmError.value) return
  if (captchaError.value) { if (!captchaReady.value) loadCaptcha(); return }
  if (mode.value === 'register' && !agreed.value) { serverError.value = '请先阅读并同意《隐私政策》'; return }
  const u = username.value.trim()
  submitting.value = true
  try {
    if (mode.value === 'register') {
      await auth.register(u, password.value, confirmPassword.value, captchaId.value, captchaCode.value)
      uni.showToast({ title: '注册成功', icon: 'success' })
    } else {
      await auth.login(u, password.value)
    }
    afterLogin()
  } catch (e) {
    const msg = e?.message || (mode.value === 'register' ? '注册失败' : '登录失败')
    serverError.value = msg
    applyLockFromMessage(msg)
    if (/已被注册/.test(msg)) usernameTaken.value = true
    if (/密码错误/.test(msg)) password.value = ''
    if (mode.value === 'register') loadCaptcha()
  } finally {
    submitting.value = false
  }
}

function goPrivacy() { uni.navigateTo({ url: '/pages/about/privacy' }) }

/** 微信一键登录：wx.login → code → /api/v1/auth/wechat/login */
function onWechatLogin() {
  if (submitting.value) return
  uni.login({
    provider: 'weixin',
    success: async (res) => {
      if (!res.code) { uni.showToast({ title: '未拿到微信 code', icon: 'none' }); return }
      submitting.value = true
      try { await auth.loginByWechat({ code: res.code }); afterLogin() }
      catch (e) { serverError.value = e?.message || '微信登录失败' }
      finally { submitting.value = false }
    },
    fail: () => uni.showToast({ title: '微信授权失败', icon: 'none' }),
  })
}
</script>

<template>
  <view class="page">
    <!-- 头部：轻量，无重色 hero -->
    <view class="head">
      <view class="head-row">
        <image class="logo" src="/static/logo-mark.png" mode="aspectFit" />
        <view class="head-text">
          <text class="brand">知源</text>
          <text class="tagline">看得懂的论文 AI 率检测</text>
        </view>
      </view>
    </view>

    <!-- 表单卡：纯白圆角卡（参考 Sign in 版式） -->
    <view class="card">
      <view class="card-head">
        <text class="card-title">{{ mode === 'login' ? '登录' : '注册' }}</text>
        <text class="card-sub">{{ mode === 'login' ? '登录后即可检测报告、问小白~' : '一分钟注册，课题阶段免费使用' }}</text>
      </view>

      <view class="fld">
        <view class="ctl" :class="{ focus: focusField === 'username', error: usernameError, ok: mode === 'register' && usernameTaken === false && !usernameError }">
          <view class="lead lead-user" />
          <input v-model="username" class="inp" placeholder="账号/邮箱" placeholder-style="color: #6E6E73" :cursor-spacing="24" :adjust-position="true" @focus="onFocus('username')" @blur="onBlur('username')" />
          <text v-if="mode === 'register' && checkingName" class="ctl-side muted">查重中…</text>
          <text v-else-if="mode === 'register' && usernameTaken === false && USERNAME_RE.test(username.trim())" class="ctl-side okmark">可用</text>
        </view>
        <text v-if="usernameError" class="err">{{ usernameError }}</text>
      </view>

      <view class="fld">
        <view class="ctl" :class="{ focus: focusField === 'password', error: passwordError }">
          <view class="lead lead-lock" />
          <input v-model="password" class="inp" :placeholder="mode === 'register' ? '设置密码' : '请输入密码'" :password="!showPwd" placeholder-style="color: #6E6E73" :cursor-spacing="24" :adjust-position="true" @focus="onFocus('password')" @blur="onBlur('password')" />
          <view class="eye" :class="{ slash: !showPwd }" hover-class="eye-hover" @click="showPwd = !showPwd" />
        </view>
        <text v-if="passwordError" class="err">{{ passwordError }}</text>
        <view v-if="mode === 'register' && password" class="rules">
          <text v-for="r in pwdRules" :key="r.t" class="rule" :class="{ ok: r.ok }">{{ r.ok ? '✓ ' : '· ' }}{{ r.t }}</text>
        </view>
      </view>

      <text v-if="mode === 'login'" class="forgot">忘记密码？联系管理员重置</text>

      <view v-if="mode === 'register'" class="fld">
        <view class="ctl" :class="{ focus: focusField === 'confirm', error: confirmError, ok: confirmPassword && confirmPassword === password }">
          <view class="lead lead-lock" />
          <input v-model="confirmPassword" class="inp" placeholder="再次输入密码" :password="!showPwd" placeholder-style="color: #6E6E73" :cursor-spacing="24" :adjust-position="true" @focus="onFocus('confirm')" @blur="onBlur('confirm')" />
          <text v-if="confirmPassword && confirmPassword === password" class="ctl-side okmark">一致</text>
        </view>
        <text v-if="confirmError" class="err">{{ confirmError }}</text>
      </view>

      <view v-if="!MOCK_MODE && mode === 'register'" class="fld">
        <view class="cap-row">
          <view class="ctl cap-ctl" :class="{ focus: focusField === 'captcha', error: captchaError }">
            <input v-model="captchaCode" class="inp" placeholder="4 位字符，不区分大小写" maxlength="6" placeholder-style="color: #6E6E73" :cursor-spacing="24" :adjust-position="true" @focus="onFocus('captcha')" @blur="onBlur('captcha')" />
          </view>
          <view class="cap" :class="{ stale: captchaExpired || captchaFailed }" hover-class="cap-hover" @click="loadCaptcha">
            <image v-if="captchaImg && !captchaLoading && !captchaExpired" class="cap-img" :src="captchaImg" mode="aspectFill" />
            <text v-else class="cap-hint">{{ captchaLoading ? '加载中…' : captchaExpired ? '已过期\n点击刷新' : captchaFailed ? '加载失败\n点击重试' : '获取验证码' }}</text>
          </view>
        </view>
        <text v-if="captchaError" class="err">{{ captchaError }}</text>
      </view>

      <view class="opts">
        <view class="chk" @click="remember = !remember">
          <view class="box" :class="{ on: remember }"><text v-if="remember">✓</text></view>
          <text class="chk-text">记住账号</text>
        </view>
        <view v-if="mode === 'register'" class="chk" @click="agreed = !agreed">
          <view class="box" :class="{ on: agreed }"><text v-if="agreed">✓</text></view>
          <text class="chk-text">同意</text><text class="link" @click.stop="goPrivacy">《隐私政策》</text>
        </view>
      </view>

      <view v-if="serverError || lockLeft > 0" class="alert">
        <text class="alert-text">{{ serverError || '登录已暂时锁定' }}</text>
        <text v-if="lockLeft > 0" class="alert-lock">{{ lockText }} 后可重试</text>
      </view>

      <button class="submit" :class="{ disabled: !canSubmit }" :disabled="!canSubmit" :loading="submitting" @click="onSubmit">
        {{ lockLeft > 0 ? `已锁定 ${lockText}` : mode === 'login' ? '登 录' : '注册并登录' }}
      </button>

      <view class="divider"><text class="divider-text">或</text></view>
      <text class="social-label">使用微信快捷登录</text>
      <view class="social-row">
        <view class="social-btn" hover-class="social-hover" @click="onWechatLogin">
          <view class="wechat-icon" />
        </view>
      </view>

      <view class="foot">
        <text class="foot-label">{{ mode === 'login' ? '还没有账号？' : '已有账号？' }}</text>
        <text class="foot-action" @click="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? '立即注册' : '去登录' }}</text>
      </view>

      <text class="terms">登录即表示你已阅读并同意<text class="terms-link" @click="goPrivacy">《隐私政策》</text></text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
/* ============================================================
 * Sign in 版式 · 白卡 + 灰色填充输入框 + 黑色胶囊按钮
 *   画布 = 浅灰；卡片 = 纯白；输入 = 灰色填充；主色 = 近黑（单色）
 * ============================================================ */
$si-canvas:    #F2F2F7;
$si-card:      #FFFFFF;
$si-field:     #F2F2F4;
$si-ink:       #0A0A0A;
$si-ink-soft:  #6E6E73;
$si-ink-faint: #8E8E93;
$si-line:      #E5E5EA;
$si-ring:      rgba(10, 10, 10, 0.08);

/* 页面：纯浅灰画布 */
.page {
  position: relative;
  min-height: 100vh;
  background: $si-canvas;
  padding-bottom: #{"calc(64rpx + env(safe-area-inset-bottom))"};
}

/* 头部 */
.head { padding: #{"calc(88rpx + env(safe-area-inset-top))"} $sp-6 0; }
.head-row { display: flex; align-items: center; gap: $sp-3; }
.logo { width: 76rpx; height: 76rpx; flex: none; }
.head-text { display: flex; flex-direction: column; }
.brand { font-size: $fs-title-3; font-weight: $fw-bold; color: $si-ink; letter-spacing: $tracking-tight; line-height: 1.15; }
.tagline { font-size: $fs-footnote; color: $si-ink-soft; margin-top: 4rpx; }

/* 表单卡：纯白圆角卡 */
.card {
  margin: $sp-6 $sp-4 0;
  padding: $sp-6 $sp-5 $sp-5;
  border-radius: $radius-xl;
  background: $si-card;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.04), 0 20rpx 48rpx rgba(0, 0, 0, 0.06);
}
.card-head { margin-bottom: $sp-5; }
.card-title { display: block; font-size: $fs-title-2; font-weight: $fw-bold; color: $si-ink; letter-spacing: $tracking-tight; }
.card-sub { display: block; margin-top: 10rpx; font-size: $fs-footnote; color: $si-ink-soft; line-height: $lh-normal; }

/* 字段：灰色填充输入框（无边框，聚焦才出黑描边） */
.fld { margin-bottom: $sp-3; }
.ctl {
  display: flex; align-items: center; gap: $sp-2;
  height: $size-input-h; padding: 0 $sp-3;
  border-radius: $radius-lg;
  background: $si-field;
  border: $stroke-thin solid transparent;
  transition: background $duration-fast $ease-standard, border-color $duration-fast $ease-standard, box-shadow $duration-fast $ease-standard;
  &.focus { border-color: $si-ink; box-shadow: 0 0 0 6rpx $si-ring; }
  &.error { border-color: $danger-solid; }
  &.ok { border-color: rgba(52, 199, 89, 0.6); }
}
.lead {
  flex: none; width: 36rpx; height: 36rpx;
  background-repeat: no-repeat; background-position: center; background-size: contain;
}
.lead-user { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='8' r='4'/><path d='M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6'/></svg>"); }
.lead-lock { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='10' width='16' height='11' rx='3'/><path d='M8 10V7a4 4 0 0 1 8 0v3'/></svg>"); }
.inp { flex: 1; min-width: 0; height: 100%; font-size: $fs-body; color: $si-ink; }
.ctl-side { flex: none; font-size: $fs-caption-1; }
.okmark { color: $success-fg; font-weight: $fw-semibold; }
.eye {
  flex: none; width: 40rpx; height: 40rpx; margin-left: $sp-1;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z'/><circle cx='12' cy='12' r='3'/></svg>") no-repeat center / contain;
  &.slash { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24'/><line x1='1' y1='1' x2='23' y2='23'/></svg>"); }
}
.eye-hover { opacity: 0.55; }
.err { display: block; margin-top: 6rpx; font-size: $fs-caption-1; color: $danger-fg; }
.forgot { display: block; margin: -8rpx 0 $sp-3; font-size: $fs-footnote; color: $si-ink-soft; }
.rules { display: flex; flex-wrap: wrap; gap: 6rpx $sp-3; margin-top: 8rpx; }
.rule { font-size: $fs-caption-1; color: $si-ink-faint; &.ok { color: $success-fg; } }

/* 验证码 */
.cap-row { display: flex; gap: $sp-2; }
.cap-ctl { flex: 1; }
.cap {
  flex: none; width: 220rpx; height: $size-input-h; border-radius: $radius-lg; overflow: hidden;
  background: $si-field; border: $stroke-thin solid transparent;
  display: flex; align-items: center; justify-content: center;
  &.stale { border-color: $warning-solid; }
}
.cap-hover { opacity: 0.7; }
.cap-img { width: 100%; height: 100%; }
.cap-hint { font-size: $fs-caption-1; color: $si-ink-soft; text-align: center; line-height: 1.3; white-space: pre-line; }

/* 勾选项 */
.opts { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: $sp-2; margin: $sp-2 0 0; }
.chk { display: flex; align-items: center; gap: 10rpx; }
.box {
  width: 34rpx; height: 34rpx; border-radius: 10rpx; border: 2rpx solid $si-ink-faint;
  display: flex; align-items: center; justify-content: center;
  &.on { background: $si-ink; border-color: $si-ink; }
  text { color: #fff; font-size: 22rpx; line-height: 1; }
}
.chk-text { font-size: $fs-footnote; color: $si-ink-soft; }
.link { font-size: $fs-footnote; color: $si-ink; font-weight: $fw-medium; text-decoration: underline; }
.muted { font-size: $fs-caption-1; color: $si-ink-faint; }

/* 错误 / 锁定提示 */
.alert { margin-top: $sp-3; padding: $sp-3; border-radius: $radius-md; background: $danger-bg; display: flex; flex-direction: column; gap: 4rpx; }
.alert-text { font-size: $fs-footnote; color: $danger-fg; line-height: $lh-normal; }
.alert-lock { font-size: $fs-footnote; color: $danger-fg; font-weight: $fw-semibold; }

/* 主按钮：黑色胶囊 */
.submit {
  margin-top: $sp-5; height: $size-btn-h-lg; line-height: $size-btn-h-lg;
  background: $si-ink; color: #fff;
  font-size: $fs-headline; font-weight: $fw-semibold;
  border-radius: $radius-pill; letter-spacing: $tracking-normal;
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;
  &::after { border: none; }
  &:active { transform: scale(#{$tap-scale}); opacity: 0.88; }
  &.disabled { opacity: 0.35; }
}

/* 微信快捷登录 */
.divider { display: flex; align-items: center; margin: $sp-5 0 $sp-3; &::before, &::after { content: ''; flex: 1; height: $stroke-hairline; background: $si-line; } }
.divider-text { padding: 0 $sp-3; font-size: $fs-caption-1; color: $si-ink-faint; }
.social-label { display: block; text-align: center; font-size: $fs-footnote; color: $si-ink-soft; margin-bottom: $sp-3; }
.social-row { display: flex; justify-content: center; gap: $sp-3; }
.social-btn {
  width: 96rpx; height: 96rpx; border-radius: $radius-lg;
  background: $si-field;
  display: flex; align-items: center; justify-content: center;
  transition: background $duration-fast $ease-standard;
}
.social-hover { background: rgba(116, 116, 128, 0.16); }
.wechat-icon {
  width: 44rpx; height: 44rpx;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%230A0A0A'><path d='M9.5 4C5.4 4 2 6.6 2 10c0 1.8 1 3.5 2.6 4.6L4 17l2.7-1.4c.9.2 1.8.3 2.8.3.3 0 .6 0 .9-.1-.2-.6-.4-1.3-.4-2 0-3.3 3.3-6 7.5-6 .3 0 .6 0 .9.1C17.7 5.6 13.9 4 9.5 4zm-3 3.6c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm5.5 0c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1z'/><path d='M22 14c0-2.8-2.9-5-6.5-5S9 11.2 9 14s2.9 5 6.5 5c.8 0 1.6-.1 2.3-.3l2 1-.5-2C21 16.7 22 15.4 22 14zm-9-1.4c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.4-.8.8-.8zm4.5 0c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.3-.8.8-.8z'/></svg>") no-repeat center / contain;
}

/* 底部切换（方案 A）：分隔线 + 放大跳转字号；再下一行是条款小字 */
.foot { margin-top: $sp-5; padding-top: $sp-4; border-top: $stroke-hairline solid $si-line; display: flex; align-items: center; justify-content: center; gap: $sp-2; }
.foot-label { font-size: $fs-footnote; color: $si-ink-soft; }
.foot-action { font-size: $fs-subhead; font-weight: $fw-semibold; color: $si-ink; text-decoration: underline; }
.terms { display: block; margin-top: $sp-3; text-align: center; font-size: $fs-caption-1; color: $si-ink-soft; line-height: $lh-normal; }
.terms-link { color: $si-ink; text-decoration: underline; }
</style>