<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha, checkUsername } from '@/api/auth'

/**
 * 登录 / 注册页
 *
 * 逻辑约束：
 *   - 已登录直接跳转，不再展示表单
 *   - 验证码未加载 / 已过期（5 分钟）时禁止提交，提示点击刷新；每次提交失败换一张
 *   - 服务端锁定（「请 N 分钟后再试」）解析成倒计时，倒计时内禁用按钮
 *   - 注册用户名实时查重（防抖 400ms）；密码规则逐条勾选
 *   - redirect 只接受站内路径（以单个 / 开头）
 *   - 提交中屏蔽重复提交（按钮与回车两条路径）
 */

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const REMEMBER_KEY = 'remember_username'
const CAPTCHA_TTL_MS = 5 * 60 * 1000
const USERNAME_RE = /^[A-Za-z0-9_.@-]{2,64}$/

type Mode = 'login' | 'register'
const mode = ref<Mode>(route.query.mode === 'register' ? 'register' : 'login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPwd = ref(false)
const capsLock = ref(false)
const remember = ref(true)
const agreed = ref(false)
const touched = ref<Record<string, boolean>>({})
const submitting = ref(false)
const serverError = ref('')

const usernameInput = ref<HTMLInputElement | null>(null)
const passwordInput = ref<HTMLInputElement | null>(null)
const captchaInput = ref<HTMLInputElement | null>(null)

const VALUE_PROPS = [
  { icon: '🔍', t: '不只给一个比例', d: '逐段解释为什么像 AI，定位最可疑的句子' },
  { icon: '🧭', t: '溯源哪家大模型', d: '疑似 GPT / 通义 / DeepSeek，知道像谁才知道怎么不像' },
  { icon: '🛡️', t: '原创被误判有路可走', d: '一键整理申诉材料，不推销「降 AI」' },
]
const LINES = ['本科 20%', '硕士 15%', '博士 10%']

/* ---------- 安全的 redirect ---------- */
const redirectTarget = computed(() => {
  const r = String(route.query.redirect || '')
  return r.startsWith('/') && !r.startsWith('//') && !r.startsWith('/login') ? r : '/dashboard'
})

/* ---------- 验证码 ---------- */
const captchaId = ref('')
const captchaImg = ref('')
const captchaCode = ref('')
const captchaLoading = ref(false)
const captchaFailed = ref(false)
const captchaExpired = ref(false)
let captchaTimer: ReturnType<typeof setTimeout> | null = null

async function loadCaptcha(focus = false) {
  if (captchaTimer) { clearTimeout(captchaTimer); captchaTimer = null }
  captchaLoading.value = true
  captchaFailed.value = false
  captchaExpired.value = false
  captchaCode.value = ''
  try {
    const c = await getCaptcha()
    captchaId.value = c.captchaId
    captchaImg.value = c.imageBase64
    captchaTimer = setTimeout(() => { captchaExpired.value = true }, CAPTCHA_TTL_MS)
  } catch {
    captchaId.value = ''
    captchaImg.value = ''
    captchaFailed.value = true
  } finally {
    captchaLoading.value = false
    if (focus) nextTick(() => captchaInput.value?.focus())
  }
}
const captchaReady = computed(() => !!captchaId.value && !captchaExpired.value && !captchaLoading.value)

/* ---------- 锁定倒计时 ---------- */
const lockUntil = ref(0)
const now = ref(Date.now())
let tick: ReturnType<typeof setInterval> | null = null
const lockLeft = computed(() => Math.max(0, Math.ceil((lockUntil.value - now.value) / 1000)))
const lockText = computed(() => {
  const s = lockLeft.value
  return s > 0 ? `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}` : ''
})
function applyLockFromMessage(msg: string) {
  const m = msg.match(/(\d+)\s*分钟/)
  if (!m || !/锁定|次数过多/.test(msg)) return
  lockUntil.value = Date.now() + Number(m[1]) * 60 * 1000
}

/* ---------- 用户名查重（注册） ---------- */
const usernameTaken = ref<boolean | null>(null)
const checkingName = ref(false)
let nameTimer: ReturnType<typeof setTimeout> | null = null
watch([username, mode], ([u, m]) => {
  usernameTaken.value = null
  if (nameTimer) clearTimeout(nameTimer)
  const v = u.trim()
  if (m !== 'register' || !USERNAME_RE.test(v)) return
  nameTimer = setTimeout(async () => {
    checkingName.value = true
    try { usernameTaken.value = !(await checkUsername(v)) } catch { usernameTaken.value = null } finally { checkingName.value = false }
  }, 400)
})

/* ---------- 校验 ---------- */
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
const PWD_RULES = computed(() => {
  const p = password.value
  return [
    { ok: p.length >= 6 && p.length <= 32, t: '6-32 位' },
    { ok: /[A-Za-z]/.test(p), t: '含字母' },
    { ok: /[0-9]/.test(p), t: '含数字' },
    { ok: !!p && p.toLowerCase() !== username.value.trim().toLowerCase(), t: '不同于账号' },
  ]
})
const pwdRulesOk = computed(() => PWD_RULES.value.every((r) => r.ok))
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
  if (mode.value !== 'register' || !touched.value.captcha) return ''
  if (!captchaReady.value) return captchaExpired.value ? '验证码已过期，点击图片刷新' : '验证码未加载，点击右侧获取'
  if (!captchaCode.value.trim()) return '请输入验证码'
  return ''
})
const formValid = computed(() => {
  if (!username.value.trim() || !password.value) return false
  if (mode.value === 'register' && (!captchaReady.value || !captchaCode.value.trim())) return false
  if (mode.value === 'register') {
    if (!USERNAME_RE.test(username.value.trim()) || usernameTaken.value) return false
    if (!pwdRulesOk.value || confirmPassword.value !== password.value || !agreed.value) return false
  }
  return true
})
const canSubmit = computed(() => formValid.value && !submitting.value && lockLeft.value === 0)

/* ---------- 生命周期 ---------- */
onMounted(() => {
  if (auth.token) { router.replace(redirectTarget.value); return }
  try {
    const saved = localStorage.getItem(REMEMBER_KEY)
    if (saved) { username.value = saved; remember.value = true }
  } catch { /* ignore */ }
  tick = setInterval(() => { now.value = Date.now() }, 1000)
  if (mode.value === 'register') loadCaptcha()
  nextTick(() => (username.value ? passwordInput.value : usernameInput.value)?.focus())
})
onUnmounted(() => {
  if (tick) clearInterval(tick)
  if (captchaTimer) clearTimeout(captchaTimer)
  if (nameTimer) clearTimeout(nameTimer)
})

watch(mode, (m) => {
  serverError.value = ''
  touched.value = {}
  confirmPassword.value = ''
  router.replace({ query: { ...route.query, mode: m === 'register' ? 'register' : undefined } })
  if (m === 'register' && !captchaReady.value) loadCaptcha()
})

function onPwdKey(e: KeyboardEvent) {
  if (typeof e.getModifierState === 'function') capsLock.value = e.getModifierState('CapsLock')
}

async function onSubmit() {
  if (submitting.value) return
  touched.value = { username: true, password: true, confirm: true, captcha: true }
  serverError.value = ''
  if (lockLeft.value > 0) return
  if (usernameError.value) { usernameInput.value?.focus(); return }
  if (passwordError.value) { passwordInput.value?.focus(); return }
  if (confirmError.value) return
  if (captchaError.value) { if (!captchaReady.value) loadCaptcha(true); else captchaInput.value?.focus(); return }
  if (mode.value === 'register' && !agreed.value) { serverError.value = '请先阅读并同意《隐私政策》'; return }

  const u = username.value.trim()
  submitting.value = true
  try {
    if (mode.value === 'register') {
      await auth.register(u, password.value, confirmPassword.value, captchaId.value, captchaCode.value)
      ElMessage.success('注册成功，已自动登录')
    } else {
      await auth.login(u, password.value)
    }
    try {
      if (remember.value) localStorage.setItem(REMEMBER_KEY, u)
      else localStorage.removeItem(REMEMBER_KEY)
    } catch { /* ignore */ }
    router.replace(redirectTarget.value)
  } catch (e: any) {
    const msg: string = e?.message || (mode.value === 'register' ? '注册失败' : '登录失败')
    serverError.value = msg
    applyLockFromMessage(msg)
    if (/已被注册/.test(msg)) usernameTaken.value = true
    // 验证码一次性，失败后必须换一张；密码错则清空密码重输
    if (/密码错误/.test(msg)) { password.value = ''; nextTick(() => passwordInput.value?.focus()) }
    if (mode.value === 'register') loadCaptcha(!/密码错误/.test(msg))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <aside class="side">
      <router-link to="/" class="side-brand"><img src="/logo-mark.png" alt="" class="side-logo" /><span>知源</span><small>看得懂的 AI 率检测</small></router-link>
      <div class="side-body">
        <h1 class="side-title">不只告诉你 AI 率，<br />还告诉你为什么、哪一段、怎么改。</h1>
        <div class="props">
          <div v-for="p in VALUE_PROPS" :key="p.t" class="prop"><span class="prop-icon">{{ p.icon }}</span><div class="prop-text"><b>{{ p.t }}</b><span>{{ p.d }}</span></div></div>
        </div>
        <div class="lines"><span class="lines-label">教育部 2026 新规红线</span><span v-for="l in LINES" :key="l" class="line-chip">{{ l }}</span></div>
      </div>
      <div class="side-foot">
        <img src="/xiaobai.gif" alt="" class="xb" />
        <div class="bubble">超标不等于作弊。先看哪几段贡献最大，再决定怎么改。<i>小白 · 检测助手</i></div>
      </div>
    </aside>

    <main class="panel">
      <div class="card">
        <div class="card-head">
          <div class="card-title">{{ mode === 'login' ? '登录' : '注册' }}</div>
          <div class="card-sub">{{ mode === 'login' ? '登录后即可检测报告、问小白~' : '一分钟注册，课题阶段免费使用' }}</div>
        </div>

        <form class="form" novalidate @submit.prevent="onSubmit">
          <div class="fld">
            <span class="ctl" :class="{ error: usernameError, ok: mode === 'register' && usernameTaken === false && !usernameError }">
              <span class="lead lead-user" aria-hidden="true" />
              <input ref="usernameInput" v-model="username" class="inp" placeholder="账号/邮箱" aria-label="账号" autocomplete="username" :aria-invalid="!!usernameError" @blur="touched.username = true" />
              <span v-if="mode === 'register' && checkingName" class="ctl-side muted">查重中…</span>
              <span v-else-if="mode === 'register' && usernameTaken === false && USERNAME_RE.test(username.trim())" class="ctl-side okmark">可用</span>
            </span>
            <span v-if="usernameError" class="err">{{ usernameError }}</span>
          </div>

          <div class="fld">
            <span class="ctl" :class="{ error: passwordError }">
              <span class="lead lead-lock" aria-hidden="true" />
              <input ref="passwordInput" v-model="password" class="inp" :type="showPwd ? 'text' : 'password'" :placeholder="mode === 'register' ? '设置密码' : '请输入密码'" aria-label="密码" :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" :aria-invalid="!!passwordError" @blur="touched.password = true" @keyup="onPwdKey" @keydown="onPwdKey" />
              <button type="button" class="eye" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">
                <svg v-if="showPwd" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" /><circle cx="12" cy="12" r="3" /></svg>
                <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 3l18 18M10.6 10.6a3 3 0 0 0 4.2 4.2M9.9 5.1A10.4 10.4 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.3 6.3C3.6 8.3 2 12 2 12s3.5 7 10 7c1.4 0 2.7-.3 3.8-.7" /></svg>
              </button>
            </span>
            <span v-if="passwordError" class="err">{{ passwordError }}</span>
            <span v-if="capsLock" class="caps">大写锁定已开启</span>
            <span v-if="mode === 'register' && password" class="rules">
              <span v-for="r in PWD_RULES" :key="r.t" class="rule" :class="{ ok: r.ok }"><i>{{ r.ok ? '✓' : '·' }}</i>{{ r.t }}</span>
            </span>
          </div>

          <span v-if="mode === 'login'" class="forgot">忘记密码？联系管理员重置</span>

          <transition name="drop">
            <div v-if="mode === 'register'" class="fld">
              <span class="ctl" :class="{ error: confirmError, ok: confirmPassword && confirmPassword === password }">
                <span class="lead lead-lock" aria-hidden="true" />
                <input v-model="confirmPassword" class="inp" :type="showPwd ? 'text' : 'password'" placeholder="再次输入密码" aria-label="确认密码" autocomplete="new-password" :aria-invalid="!!confirmError" @blur="touched.confirm = true" />
                <span v-if="confirmPassword && confirmPassword === password" class="ctl-side okmark">一致</span>
              </span>
              <span v-if="confirmError" class="err">{{ confirmError }}</span>
            </div>
          </transition>

          <div v-if="mode === 'register'" class="fld">
            <div class="cap-row">
              <span class="ctl cap-ctl" :class="{ error: captchaError }">
                <input ref="captchaInput" v-model="captchaCode" class="inp" placeholder="4 位字符，不区分大小写" aria-label="验证码" maxlength="6" autocomplete="off" :aria-invalid="!!captchaError" @blur="touched.captcha = true" />
              </span>
              <button type="button" class="cap" :class="{ stale: captchaExpired || captchaFailed }" :disabled="captchaLoading" title="看不清？点击换一张" @click="loadCaptcha(true)">
                <img v-if="captchaImg && !captchaLoading" :src="captchaImg" alt="验证码" />
                <span class="cap-overlay">{{ captchaLoading ? '加载中…' : captchaExpired ? '已过期，点击刷新' : captchaFailed ? '加载失败，点击重试' : captchaImg ? '换一张' : '获取验证码' }}</span>
              </button>
            </div>
            <span v-if="captchaError" class="err">{{ captchaError }}</span>
          </div>

          <div class="opts">
            <label class="chk"><input v-model="remember" type="checkbox" /><i /> 记住账号</label>
            <label v-if="mode === 'register'" class="chk"><input v-model="agreed" type="checkbox" /><i /> 同意<router-link to="/privacy" target="_blank" class="link">《隐私政策》</router-link></label>
          </div>

          <transition name="drop">
            <div v-if="serverError || lockLeft > 0" class="alert" role="alert">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
              <span>{{ serverError || '登录已暂时锁定' }}<b v-if="lockLeft > 0" class="lock">{{ lockText }} 后可重试</b></span>
            </div>
          </transition>

          <button type="submit" class="primary" :disabled="!canSubmit">
            <span v-if="submitting" class="spin" />
            <span v-else>{{ lockLeft > 0 ? `已锁定 ${lockText}` : mode === 'login' ? '登 录' : '注册并登录' }}</span>
          </button>

          <div class="foot">
            <span class="foot-label">{{ mode === 'login' ? '还没有账号？' : '已有账号？' }}</span>
            <a class="foot-action" @click="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? '立即注册' : '去登录' }}</a>
          </div>

          <span class="terms">登录即表示你已阅读并同意<router-link to="/privacy" target="_blank" class="terms-link">《隐私政策》</router-link></span>
        </form>
      </div>
      <router-link to="/" class="back-home">返回首页</router-link>
    </main>
  </div>
</template>

<style scoped>
/* ============================================================
 * Sign in 版式 · 白卡 + 灰色填充输入框 + 黑色胶囊按钮
 *   画布 = 浅灰；卡片 = 纯白；输入 = 灰色填充；主色 = 近黑（单色）
 * ============================================================ */
.login-page {
  --si-canvas: #F2F2F7;
  --si-card: #FFFFFF;
  --si-field: #F2F2F4;
  --si-ink: #0A0A0A;
  --si-ink-soft: #6E6E73;
  --si-ink-faint: #8E8E93;
  --si-line: #E5E5EA;
  --si-ring: rgba(10, 10, 10, .08);

  position: relative;
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 11fr) minmax(0, 13fr);
  background: var(--si-canvas);
  color: var(--si-ink);
}

/* ---------- 左栏：品牌与价值主张（平面，无玻璃/无光晕） ---------- */
.side { position: relative; padding: 44px 56px; display: flex; flex-direction: column; }
.side-brand { display: inline-flex; align-items: center; gap: 10px; color: var(--si-ink); text-decoration: none; }
.side-brand span { font-weight: 700; font-size: 20px; letter-spacing: -0.3px; }
.side-brand small { font-size: 12px; color: var(--si-ink-soft); padding-left: 10px; border-left: 1px solid var(--si-line); }
.side-logo { width: 34px; height: 34px; object-fit: contain; }

.side-body { margin: auto 0; padding: 48px 0; }
.side-title { font-size: 32px; line-height: 1.28; letter-spacing: -0.8px; margin: 0 0 32px; font-weight: 700; color: var(--si-ink); }

.props { display: flex; flex-direction: column; gap: 18px; }
.prop { display: flex; gap: 14px; align-items: flex-start; }
.prop-icon { flex: none; width: 36px; height: 36px; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; border-radius: 10px; background: #fff; }
.prop-text b { display: block; font-size: 15px; font-weight: 600; margin-bottom: 3px; color: var(--si-ink); }
.prop-text span { font-size: 13px; color: var(--si-ink-soft); line-height: 1.55; }

.lines { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 30px; }
.lines-label { font-size: 12px; color: var(--si-ink-soft); margin-right: 2px; }
.line-chip { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 9999px; background: #fff; color: var(--si-ink-soft); }

.side-foot { display: flex; align-items: center; gap: 12px; }
.xb { width: 40px; height: 40px; border-radius: 50%; object-fit: cover; background: #fff; flex: none; }
.bubble { position: relative; font-size: 13px; line-height: 1.5; padding: 10px 14px; border-radius: 14px; color: var(--si-ink-soft); background: #fff; }
.bubble i { display: block; font-style: normal; font-size: 11px; color: var(--si-ink-faint); margin-top: 2px; }
.bubble::before { content: ''; position: absolute; left: -6px; top: 14px; border: 6px solid transparent; border-right-color: #fff; border-left: 0; }

/* ---------- 右栏：纯白卡片 ---------- */
.panel { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px 24px; gap: 16px; }
.card {
  width: 100%; max-width: 420px;
  padding: 36px 32px 30px;
  border-radius: 20px;
  background: var(--si-card);
  box-shadow: 0 1px 2px rgba(0, 0, 0, .04), 0 12px 32px rgba(0, 0, 0, .06);
}
.card-head { margin-bottom: 26px; }
.card-title { font-size: 26px; font-weight: 700; letter-spacing: -0.6px; color: var(--si-ink); }
.card-sub { font-size: 14px; color: var(--si-ink-soft); margin-top: 6px; }

/* ---------- 表单 ---------- */
.form { display: flex; flex-direction: column; gap: 14px; }
.fld { display: flex; flex-direction: column; gap: 6px; }
.caps { font-size: 12px; color: #B26200; }

/* 输入框：灰色填充，默认无边框，聚焦出黑描边 */
.ctl { display: flex; align-items: center; gap: 10px; box-sizing: border-box; height: 48px; padding: 0 14px; border-radius: 12px; background: var(--si-field); border: 1.5px solid transparent; transition: border-color .2s, box-shadow .2s; }
.ctl:focus-within { border-color: var(--si-ink); box-shadow: 0 0 0 3px var(--si-ring); }
.ctl.error { border-color: var(--system-red); }
.ctl.ok { border-color: rgba(52, 199, 89, .6); }

.lead { flex: none; width: 18px; height: 18px; background-repeat: no-repeat; background-position: center; background-size: contain; }
.lead-user { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='8' r='4'/><path d='M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6'/></svg>"); }
.lead-lock { background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%236E6E73' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='4' y='10' width='16' height='11' rx='3'/><path d='M8 10V7a4 4 0 0 1 8 0v3'/></svg>"); }

/* 去掉浏览器自动填充的蓝底（#E8F0FE）：裁进文字字形 + 超长 transition 延迟上色 */
.inp:-webkit-autofill,
.inp:-webkit-autofill:hover,
.inp:-webkit-autofill:focus,
.inp:-webkit-autofill:active {
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: var(--si-ink);
  caret-color: var(--si-ink);
  transition: background-color 9999s ease-in-out 0s, color 9999s ease-in-out 0s;
}
.inp { flex: 1; min-width: 0; border: none; background: transparent; outline: none; font-size: 15px; color: var(--si-ink); font-family: inherit; height: 100%; }
.inp::placeholder { color: var(--si-ink-soft); }
.ctl-side { flex: none; font-size: 12px; }
.okmark { color: #1B7F3E; font-weight: 600; }
.eye { flex: none; border: none; background: transparent; color: var(--si-ink-soft); cursor: pointer; padding: 4px; display: inline-flex; border-radius: 6px; }
.eye:hover { color: var(--si-ink); }
.err { font-size: 12px; color: var(--system-red); }
.forgot { font-size: 13px; color: var(--si-ink-soft); }
.rules { display: flex; flex-wrap: wrap; gap: 6px 12px; margin-top: 2px; }
.rule { font-size: 12px; color: var(--si-ink-faint); display: inline-flex; align-items: center; gap: 4px; }
.rule i { font-style: normal; width: 14px; text-align: center; }
.rule.ok { color: #1B7F3E; }

.cap-row { display: flex; gap: 10px; }
.cap-ctl { flex: 1; }
.cap { position: relative; flex: none; width: 118px; height: 48px; border-radius: 12px; border: 1.5px solid transparent; background: var(--si-field); padding: 0; overflow: hidden; cursor: pointer; }
.cap img { width: 100%; height: 100%; object-fit: cover; display: block; }
.cap-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 12px; color: var(--si-ink); background: rgba(255, 255, 255, .92); opacity: 0; transition: opacity .15s; padding: 0 6px; text-align: center; line-height: 1.3; }
.cap:hover .cap-overlay, .cap.stale .cap-overlay, .cap:not(:has(img)) .cap-overlay { opacity: 1; }
.cap.stale { border-color: var(--system-orange); }

.opts { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 13px; }
.chk { display: inline-flex; align-items: center; gap: 6px; color: var(--si-ink-soft); cursor: pointer; user-select: none; }
.chk input { position: absolute; opacity: 0; width: 0; height: 0; }
.chk i { width: 16px; height: 16px; border-radius: 5px; border: 1.5px solid var(--si-ink-faint); display: inline-flex; align-items: center; justify-content: center; transition: all .15s; }
.chk input:checked + i { background: var(--si-ink); border-color: var(--si-ink); }
.chk input:checked + i::after { content: ''; width: 4px; height: 8px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg) translate(-1px, -1px); }
.link { color: var(--si-ink); text-decoration: underline; cursor: pointer; margin-left: 2px; }
.muted { color: var(--si-ink-faint); }

.alert { display: flex; align-items: flex-start; gap: 8px; padding: 10px 12px; border-radius: 10px; background: rgba(255, 59, 48, .08); color: #C62A22; font-size: 13px; line-height: 1.5; }
.alert svg { flex: none; margin-top: 2px; }
.lock { display: block; font-weight: 600; margin-top: 2px; }

/* 主按钮：黑色胶囊 */
.primary { position: relative; height: 50px; border: none; border-radius: 9999px; color: #fff; font-size: 16px; font-weight: 600; font-family: inherit; cursor: pointer; background: var(--si-ink); transition: background .2s, transform .15s, opacity .2s; margin-top: 6px; }
.primary:hover:not(:disabled) { background: #262626; }
.primary:active:not(:disabled) { transform: scale(.985); }
.primary:disabled { opacity: .35; cursor: not-allowed; }
.spin { display: inline-block; width: 18px; height: 18px; border-radius: 50%; border: 2px solid rgba(255, 255, 255, .4); border-top-color: #fff; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 底部：切换（分隔线 + 放大字号）与条款小字 */
.foot { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 14px; padding-top: 16px; border-top: 1px solid var(--si-line); }
.foot-label { font-size: 13px; color: var(--si-ink-soft); }
.foot-action { font-size: 15px; font-weight: 600; color: var(--si-ink); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
.terms { display: block; margin-top: 12px; text-align: center; font-size: 12px; color: var(--si-ink-soft); line-height: 1.5; }
.terms-link { color: var(--si-ink); text-decoration: underline; }

.back-home { font-size: 13px; color: var(--si-ink-soft); text-decoration: none; transition: color .15s; }
.back-home:hover { color: var(--si-ink); }

.drop-enter-active, .drop-leave-active { transition: all .22s ease; }
.drop-enter-from, .drop-leave-to { opacity: 0; transform: translateY(-6px); }

@media (max-width: 960px) {
  .login-page { grid-template-columns: 1fr; }
  .side { display: none; }
  .panel { justify-content: flex-start; padding-top: 56px; }
  .card { padding: 28px 22px 24px; }
}
</style>