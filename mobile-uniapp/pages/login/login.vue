<script setup>
import { ref, computed, watch } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'
import { http, MOCK_MODE } from '@/utils/request'

/*
 * 登录 / 注册页
 *   逻辑：已登录直跳 · 验证码 5 分钟过期禁提交 · 失败换图 · 锁定倒计时 · 注册用户名查重 · 规则逐条勾选 · 来源页回跳只接受 /pages/ 路径 · 防重复提交
 *   视觉：渐变头图 + 白卡表单 + 分段滑块 + 规则勾选 + 行内错误 + 错误提示条
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
  if (MOCK_MODE || !touched.value.captcha) return ''
  if (!captchaReady.value) return captchaExpired.value ? '验证码已过期，点击图片刷新' : '验证码未加载，点击右侧获取'
  if (!captchaCode.value.trim()) return '请输入验证码'
  return ''
})
const formValid = computed(() => {
  if (!username.value.trim() || !password.value) return false
  if (!MOCK_MODE && (!captchaReady.value || !captchaCode.value.trim())) return false
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
  loadCaptcha()
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
  if (!captchaReady.value) loadCaptcha()
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
      await auth.login(u, password.value, captchaId.value, captchaCode.value)
    }
    afterLogin()
  } catch (e) {
    const msg = e?.message || (mode.value === 'register' ? '注册失败' : '登录失败')
    serverError.value = msg
    applyLockFromMessage(msg)
    if (/已被注册/.test(msg)) usernameTaken.value = true
    if (/密码错误/.test(msg)) password.value = ''
    loadCaptcha()
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
    <!-- 渐变头图 -->
    <view class="hero">
      <view class="orb o1" /><view class="orb o2" />
      <view class="hero-row">
        <image class="logo" src="/static/logo.png" mode="aspectFill" />
        <view class="hero-text">
          <text class="brand">知源</text>
          <text class="tagline">看得懂的论文 AI 率检测</text>
        </view>
      </view>
      <text class="hero-line">不只告诉你 AI 率，还告诉你为什么、哪一段、怎么改</text>
      <view class="chips"><text class="chip">逐段解释</text><text class="chip">溯源哪家大模型</text><text class="chip">误判可申诉</text></view>
    </view>

    <!-- 表单卡 -->
    <view class="card">
      <view class="seg">
        <view class="seg-thumb" :class="mode" />
        <text class="seg-item" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</text>
        <text class="seg-item" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</text>
      </view>

      <view class="fld">
        <text class="fld-label">账号</text>
        <view class="ctl" :class="{ error: usernameError, ok: mode === 'register' && usernameTaken === false && !usernameError }">
          <input v-model="username" class="inp" placeholder="学号 / 工号 / 邮箱" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.username = true" />
          <text v-if="mode === 'register' && checkingName" class="ctl-side muted">查重中…</text>
          <text v-else-if="mode === 'register' && usernameTaken === false && USERNAME_RE.test(username.trim())" class="ctl-side okmark">可用</text>
        </view>
        <text v-if="usernameError" class="err">{{ usernameError }}</text>
      </view>

      <view class="fld">
        <text class="fld-label">密码</text>
        <view class="ctl" :class="{ error: passwordError }">
          <input v-model="password" class="inp" :placeholder="mode === 'register' ? '设置密码' : '请输入密码'" :password="!showPwd" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.password = true" />
          <text class="eye" @click="showPwd = !showPwd">{{ showPwd ? '隐藏' : '显示' }}</text>
        </view>
        <text v-if="passwordError" class="err">{{ passwordError }}</text>
        <view v-if="mode === 'register' && password" class="rules">
          <text v-for="r in pwdRules" :key="r.t" class="rule" :class="{ ok: r.ok }">{{ r.ok ? '✓ ' : '· ' }}{{ r.t }}</text>
        </view>
      </view>

      <view v-if="mode === 'register'" class="fld">
        <text class="fld-label">确认密码</text>
        <view class="ctl" :class="{ error: confirmError, ok: confirmPassword && confirmPassword === password }">
          <input v-model="confirmPassword" class="inp" placeholder="再次输入密码" :password="!showPwd" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.confirm = true" />
          <text v-if="confirmPassword && confirmPassword === password" class="ctl-side okmark">一致</text>
        </view>
        <text v-if="confirmError" class="err">{{ confirmError }}</text>
      </view>

      <view v-if="!MOCK_MODE" class="fld">
        <text class="fld-label">验证码</text>
        <view class="cap-row">
          <view class="ctl cap-ctl" :class="{ error: captchaError }">
            <input v-model="captchaCode" class="inp" placeholder="4 位字符，不区分大小写" maxlength="6" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" @blur="touched.captcha = true" />
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
        <text v-else class="muted">忘记密码请联系管理员</text>
      </view>

      <view v-if="serverError || lockLeft > 0" class="alert">
        <text class="alert-text">{{ serverError || '登录已暂时锁定' }}</text>
        <text v-if="lockLeft > 0" class="alert-lock">{{ lockText }} 后可重试</text>
      </view>

      <button class="submit" :class="{ disabled: !canSubmit }" :disabled="!canSubmit" :loading="submitting" @click="onSubmit">
        {{ lockLeft > 0 ? `已锁定 ${lockText}` : mode === 'login' ? '登 录' : '注册并登录' }}
      </button>

      <!-- #ifdef MP-WEIXIN -->
      <view class="divider"><text class="divider-text">或</text></view>
      <button class="wechat-btn" :disabled="submitting" @click="onWechatLogin">
        <view class="wechat-icon" />
        <text class="wechat-text">微信一键登录</text>
      </button>
      <!-- #endif -->

      <view class="foot">
        <text class="foot-text">{{ mode === 'login' ? '还没有账号？' : '已有账号？' }}<text class="link" @click="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? '立即注册' : '去登录' }}</text></text>
      </view>
    </view>

    <text class="foot-note">课题阶段免费 · 不代写、不改写 · 结果仅供参考</text>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; background: $bg-grouped-primary; padding-bottom: #{"calc(60rpx + env(safe-area-inset-bottom))"}; }

/* 头图 */
.hero {
  position: relative; overflow: hidden; color: #fff;
  padding: #{"calc(120rpx + env(safe-area-inset-top))"} $sp-5 140rpx;
  background: linear-gradient(160deg, #0B1F3A 0%, #10355E 55%, #0D9488 130%);
}
.orb { position: absolute; border-radius: 50%; filter: blur(60rpx); opacity: 0.5; }
.o1 { width: 420rpx; height: 420rpx; background: #2563EB; top: -160rpx; right: -120rpx; }
.o2 { width: 300rpx; height: 300rpx; background: #14B8A6; bottom: -120rpx; left: -60rpx; opacity: 0.35; }
.hero-row { position: relative; display: flex; align-items: center; gap: $sp-3; }
.logo { width: 88rpx; height: 88rpx; border-radius: 24rpx; box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.25); flex: none; }
.hero-text { display: flex; flex-direction: column; }
.brand { font-size: $fs-title-1; font-weight: $fw-bold; letter-spacing: $tracking-tight; line-height: 1.1; }
.tagline { font-size: $fs-footnote; opacity: 0.7; margin-top: 6rpx; }
.hero-line { position: relative; display: block; margin-top: $sp-5; font-size: $fs-headline; font-weight: $fw-semibold; line-height: $lh-normal; }
.chips { position: relative; display: flex; flex-wrap: wrap; gap: $sp-2; margin-top: $sp-3; }
.chip { font-size: $fs-caption-1; padding: 6rpx $sp-3; border-radius: $radius-pill; background: rgba(255, 255, 255, 0.14); }

/* 表单卡 */
.card {
  margin: -88rpx $sp-4 0; padding: $sp-5 $sp-4 $sp-4;
  background: $bg-primary; border-radius: $radius-xl;
  box-shadow: 0 24rpx 64rpx rgba(15, 23, 42, 0.10);
  position: relative;
}
.seg { position: relative; display: flex; background: $fill-tertiary; border-radius: 20rpx; padding: 6rpx; margin-bottom: $sp-4; }
.seg-thumb { position: absolute; top: 6rpx; bottom: 6rpx; left: 6rpx; width: calc(50% - 6rpx); background: $bg-primary; border-radius: 16rpx; box-shadow: $shadow-card; transition: transform $duration-base $ease-standard; &.register { transform: translateX(100%); } }
.seg-item { position: relative; flex: 1; text-align: center; padding: 14rpx 0; font-size: $fs-subhead; color: $label-secondary; &.active { color: $label-primary; font-weight: $fw-semibold; } }

.fld { margin-bottom: $sp-3; }
.fld-label { display: block; font-size: $fs-caption-1; font-weight: $fw-medium; color: $label-secondary; margin-bottom: 8rpx; }
.ctl {
  display: flex; align-items: center; gap: $sp-2; height: 92rpx; padding: 0 $sp-3;
  border-radius: $radius-lg; background: #FAFBFC; border: $stroke-hairline solid #E3E7EC;
  &.error { border-color: $danger-solid; }
  &.ok { border-color: rgba(52, 199, 89, 0.6); }
}
.inp { flex: 1; min-width: 0; height: 100%; font-size: $fs-body; color: $label-primary; }
.ctl-side { flex: none; font-size: $fs-caption-1; } .okmark { color: $success-fg; font-weight: $fw-semibold; }
.eye { flex: none; font-size: $fs-footnote; color: $brand-primary; padding-left: $sp-2; }
.err { display: block; margin-top: 6rpx; font-size: $fs-caption-1; color: $danger-fg; }
.rules { display: flex; flex-wrap: wrap; gap: 6rpx $sp-3; margin-top: 8rpx; }
.rule { font-size: $fs-caption-1; color: $label-tertiary; &.ok { color: $success-fg; } }

.cap-row { display: flex; gap: $sp-2; }
.cap-ctl { flex: 1; }
.cap {
  flex: none; width: 220rpx; height: 92rpx; border-radius: $radius-lg; overflow: hidden;
  border: $stroke-hairline solid #E3E7EC; background: $bg-primary;
  display: flex; align-items: center; justify-content: center;
  &.stale { border-color: $warning-solid; }
}
.cap-hover { opacity: 0.7; }
.cap-img { width: 100%; height: 100%; }
.cap-hint { font-size: $fs-caption-1; color: $brand-primary; text-align: center; line-height: 1.3; white-space: pre-line; }

.opts { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: $sp-2; margin: $sp-1 0 0; }
.chk { display: flex; align-items: center; gap: 10rpx; }
.box {
  width: 34rpx; height: 34rpx; border-radius: 10rpx; border: 2rpx solid #C7CCD3;
  display: flex; align-items: center; justify-content: center;
  &.on { background: $brand-primary; border-color: $brand-primary; }
  text { color: #fff; font-size: 22rpx; line-height: 1; }
}
.chk-text { font-size: $fs-footnote; color: $label-secondary; }
.link { font-size: $fs-footnote; color: $brand-primary; }
.muted { font-size: $fs-caption-1; color: $label-tertiary; }

.alert { margin-top: $sp-3; padding: $sp-2 $sp-3; border-radius: $radius-md; background: $danger-bg; display: flex; flex-direction: column; gap: 4rpx; }
.alert-text { font-size: $fs-footnote; color: $danger-fg; line-height: $lh-normal; }
.alert-lock { font-size: $fs-footnote; color: $danger-fg; font-weight: $fw-semibold; }

.submit {
  margin-top: $sp-4; height: $size-btn-h-lg; line-height: $size-btn-h-lg;
  background: linear-gradient(135deg, #0A84FF 0%, #2563EB 100%); color: #fff;
  font-size: $fs-headline; font-weight: $fw-semibold; border-radius: 28rpx; letter-spacing: 2rpx;
  box-shadow: 0 16rpx 40rpx rgba(37, 99, 235, 0.25);
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;
  &::after { border: none; }
  &:active { transform: scale(#{$tap-scale}); opacity: 0.9; }
  &.disabled { opacity: 0.45; box-shadow: none; }
}

.divider { display: flex; align-items: center; margin: $sp-4 0 $sp-3; &::before, &::after { content: ''; flex: 1; height: $stroke-hairline; background: $separator; } }
.divider-text { padding: 0 $sp-3; font-size: $fs-caption-1; color: $label-secondary; }
.wechat-btn {
  height: $size-btn-h-lg; line-height: $size-btn-h-lg; background: #07C160; color: #fff;
  font-size: $fs-headline; font-weight: $fw-semibold; border-radius: 28rpx;
  display: flex; align-items: center; justify-content: center; gap: $sp-2;
  &::after { border: none; }
}
.wechat-icon {
  width: 40rpx; height: 40rpx;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23FFFFFF'><path d='M9.5 4C5.4 4 2 6.6 2 10c0 1.8 1 3.5 2.6 4.6L4 17l2.7-1.4c.9.2 1.8.3 2.8.3.3 0 .6 0 .9-.1-.2-.6-.4-1.3-.4-2 0-3.3 3.3-6 7.5-6 .3 0 .6 0 .9.1C17.7 5.6 13.9 4 9.5 4zm-3 3.6c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm5.5 0c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1z'/><path d='M22 14c0-2.8-2.9-5-6.5-5S9 11.2 9 14s2.9 5 6.5 5c.8 0 1.6-.1 2.3-.3l2 1-.5-2C21 16.7 22 15.4 22 14zm-9-1.4c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.4-.8.8-.8zm4.5 0c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.3-.8.8-.8z'/></svg>") no-repeat center / contain;
}

.foot { margin-top: $sp-4; text-align: center; }
.foot-text { font-size: $fs-caption-1; color: $label-secondary; }
.foot-note { display: block; margin-top: $sp-4; font-size: $fs-caption-2; color: $label-tertiary; text-align: center; }
</style>
