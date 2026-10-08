<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'

/**
 * 登录 / 注册页
 *   左栏（≥ 900px）：品牌 + 三条价值主张；右栏：表单
 *   表单：行内校验 · 密码可见切换 · 注册时密码强度与协议勾选 · 记住账号 · 验证码点击刷新
 *   服务端错误（锁定 / 验证码 / 账号停用）显示在表单内，不只靠 toast
 */

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const REMEMBER_KEY = 'remember_username'
const mode = ref<'login' | 'register'>(route.query.mode === 'register' ? 'register' : 'login')
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
const touched = ref<Record<string, boolean>>({})
const usernameInput = ref<HTMLInputElement | null>(null)
const captchaInput = ref<HTMLInputElement | null>(null)

const VALUE_PROPS = [
  { t: '不只给 AI 率', d: '逐段解释为什么像 AI，哪一句最可疑' },
  { t: '溯源哪家大模型', d: '疑似 GPT / 通义 / DeepSeek，知道像谁才知道怎么不像' },
  { t: '原创被误判有路可走', d: '一键生成申诉材料，不推销「降 AI」' },
]

/* ---------- 行内校验 ---------- */
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

/* 密码强度：长度 + 字符种类 */
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

/* ---------- 验证码 ---------- */
async function loadCaptcha() {
  captchaLoading.value = true
  captchaFailed.value = false
  try {
    const c = await getCaptcha()
    captchaId.value = c.captchaId
    captchaImg.value = c.imageBase64
  } catch {
    captchaId.value = ''
    captchaImg.value = ''
    captchaFailed.value = true
  } finally {
    captchaLoading.value = false
    captchaCode.value = ''
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(REMEMBER_KEY)
    if (saved) { username.value = saved; remember.value = true }
  } catch { /* ignore */ }
  loadCaptcha()
  nextTick(() => (username.value ? captchaInput.value : usernameInput.value)?.focus())
})

watch(mode, () => {
  serverError.value = ''
  touched.value = {}
  confirmPassword.value = ''
  if (!captchaImg.value) loadCaptcha()
})

function touchAll() {
  touched.value = { username: true, password: true, confirm: true, captcha: true }
}

async function onSubmit() {
  touchAll()
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
      ElMessage.success('注册成功，已自动登录')
    } else {
      await auth.login(u, password.value, captchaId.value, captchaCode.value)
    }
    try {
      if (remember.value) localStorage.setItem(REMEMBER_KEY, u)
      else localStorage.removeItem(REMEMBER_KEY)
    } catch { /* ignore */ }
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect.startsWith('/') ? redirect : '/dashboard')
  } catch (e: any) {
    serverError.value = e?.message || (mode.value === 'register' ? '注册失败' : '登录失败')
    // 验证码一次性：失败后必须换一张
    loadCaptcha()
    nextTick(() => captchaInput.value?.focus())
  }
}
</script>

<template>
  <div class="login-page">
    <aside class="side">
      <router-link to="/" class="side-brand"><img src="/logo.png" alt="" class="side-logo" />知源</router-link>
      <h1 class="side-title">看得懂的<br />论文 AI 率检测</h1>
      <ul class="side-props">
        <li v-for="p in VALUE_PROPS" :key="p.t"><b>{{ p.t }}</b><span>{{ p.d }}</span></li>
      </ul>
      <div class="side-foot">课题阶段免费 · 不代写、不改写 · 结果仅供参考</div>
    </aside>

    <main class="panel">
      <div class="wrap">
        <div class="hero">
          <div class="brand">{{ mode === 'login' ? '欢迎回来' : '创建账号' }}</div>
          <div class="tagline">{{ mode === 'login' ? '登录后查看报告、问小白、提交申诉' : '一分钟注册，课题阶段免费使用' }}</div>
        </div>

        <div class="seg" role="tablist">
          <button class="seg-btn" :class="{ active: mode === 'login' }" role="tab" @click="mode = 'login'">登录</button>
          <button class="seg-btn" :class="{ active: mode === 'register' }" role="tab" @click="mode = 'register'">注册</button>
        </div>

        <form class="form" novalidate @submit.prevent="onSubmit">
          <div class="field" :class="{ error: usernameError }">
            <input ref="usernameInput" v-model="username" placeholder="学号 / 工号 / 邮箱" class="apple-input" autocomplete="username" @blur="touched.username = true" />
          </div>
          <div v-if="usernameError" class="err">{{ usernameError }}</div>

          <div class="field pwd" :class="{ error: passwordError }">
            <input v-model="password" :type="showPwd ? 'text' : 'password'" :placeholder="mode === 'register' ? '设置密码（6-32 位，含字母和数字）' : '密码'" class="apple-input" :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" @blur="touched.password = true" />
            <button type="button" class="eye" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">{{ showPwd ? '隐藏' : '显示' }}</button>
          </div>
          <div v-if="passwordError" class="err">{{ passwordError }}</div>
          <div v-if="mode === 'register' && password" class="strength">
            <i v-for="n in 4" :key="n" :class="{ on: n <= strength, ['lv' + strength]: n <= strength }" />
            <span>{{ STRENGTH_LABEL[strength] }}</span>
          </div>

          <template v-if="mode === 'register'">
            <div class="field" :class="{ error: confirmError }">
              <input v-model="confirmPassword" :type="showPwd ? 'text' : 'password'" placeholder="再次输入密码" class="apple-input" autocomplete="new-password" @blur="touched.confirm = true" />
            </div>
            <div v-if="confirmError" class="err">{{ confirmError }}</div>
          </template>

          <div class="captcha-row">
            <div class="field captcha-field" :class="{ error: captchaError }">
              <input ref="captchaInput" v-model="captchaCode" placeholder="验证码" class="apple-input" maxlength="6" autocomplete="off" @blur="touched.captcha = true" />
            </div>
            <button type="button" class="captcha-box" :disabled="captchaLoading" title="看不清？点击换一张" @click="loadCaptcha">
              <img v-if="captchaImg && !captchaLoading" :src="captchaImg" alt="验证码" />
              <span v-else-if="captchaLoading" class="captcha-hint">加载中…</span>
              <span v-else class="captcha-hint">{{ captchaFailed ? '点击重试' : '获取验证码' }}</span>
            </button>
          </div>
          <div v-if="captchaError" class="err">{{ captchaError }}</div>
          <div v-else-if="captchaFailed" class="err">验证码服务暂时不可用，点击右侧重试</div>

          <div class="opts">
            <label class="chk"><input v-model="remember" type="checkbox" /> 记住账号</label>
            <label v-if="mode === 'register'" class="chk"><input v-model="agreed" type="checkbox" /> 我已阅读并同意 <router-link to="/privacy" target="_blank" class="link">《隐私政策》</router-link></label>
            <span v-else class="muted">忘记密码？请联系学校管理员重置</span>
          </div>

          <div v-if="serverError" class="server-error" role="alert">{{ serverError }}</div>

          <el-button
            type="primary" round size="large" native-type="submit"
            :loading="auth.loading" :disabled="!canSubmit"
            style="width: 100%; margin-top: 12px; height: 50px; font-size: 17px"
          >{{ mode === 'login' ? '登 录' : '注册并登录' }}</el-button>

          <div class="footer-hint">
            {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
            <span class="switch-link" @click="mode = mode === 'login' ? 'register' : 'login'">{{ mode === 'login' ? '立即注册' : '去登录' }}</span>
          </div>
        </form>
      </div>
    </main>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); background: var(--system-background); }
.side { background: linear-gradient(160deg, #0B1F3A 0%, #10355E 55%, #0D9488 130%); color: #fff; padding: 48px 56px; display: flex; flex-direction: column; }
.side-brand { display: inline-flex; align-items: center; gap: 10px; color: #fff; text-decoration: none; font-weight: 700; font-size: 18px; letter-spacing: -0.3px; }
.side-logo { width: 28px; height: 28px; border-radius: 8px; object-fit: cover; }
.side-title { font-size: 38px; line-height: 1.2; letter-spacing: -1px; margin: 72px 0 36px; font-weight: 700; }
.side-props { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 22px; }
.side-props li { display: flex; flex-direction: column; gap: 4px; padding-left: 16px; border-left: 2px solid rgba(255, 255, 255, 0.35); }
.side-props b { font-size: 16px; } .side-props span { font-size: 14px; color: rgba(255, 255, 255, 0.72); line-height: 1.5; }
.side-foot { margin-top: auto; font-size: 12px; color: rgba(255, 255, 255, 0.55); }

.panel { display: flex; align-items: center; justify-content: center; padding: 48px 24px; }
.wrap { width: 100%; max-width: 380px; }
.hero { margin-bottom: 32px; }
.brand { font-size: var(--fs-large-title); font-weight: var(--fw-bold); letter-spacing: -0.8px; color: var(--label); line-height: 1.1; }
.tagline { font-size: var(--fs-subhead); color: var(--label-secondary); margin-top: 8px; }

.seg { display: flex; background: rgba(120, 120, 128, 0.12); border-radius: var(--radius-btn); padding: 3px; margin-bottom: 16px; }
.seg-btn { flex: 1; border: none; background: transparent; color: var(--label); font-size: var(--fs-subhead); font-weight: var(--fw-medium); padding: 8px 0; border-radius: 8px; cursor: pointer; font-family: inherit; transition: background-color var(--dur-fast); }
.seg-btn.active { background: #fff; font-weight: var(--fw-semibold); box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }

.field { background: rgba(120, 120, 128, 0.12); border-radius: var(--radius-btn); padding: 2px 16px; margin-bottom: 10px; border: 1px solid transparent; transition: border-color var(--dur-fast); }
.field:focus-within { border-color: var(--system-blue); background: #fff; }
.field.error { border-color: var(--system-red); }
.field.pwd { display: flex; align-items: center; gap: 8px; }
.eye { border: none; background: transparent; color: var(--system-blue); font-size: 13px; cursor: pointer; font-family: inherit; padding: 4px 0 4px 8px; flex: none; }
.err { margin: -6px 0 10px 6px; font-size: 12px; color: var(--system-red); }
.apple-input { width: 100%; height: 46px; border: none; background: transparent; outline: none; font-size: var(--fs-body); color: var(--label); font-family: inherit; min-width: 0; }
.apple-input::placeholder { color: var(--label-tertiary); }

.strength { display: flex; align-items: center; gap: 4px; margin: -4px 0 10px 4px; }
.strength i { width: 36px; height: 4px; border-radius: 2px; background: rgba(120, 120, 128, 0.2); }
.strength i.on.lv1 { background: var(--system-red); } .strength i.on.lv2 { background: var(--system-orange); } .strength i.on.lv3 { background: var(--system-teal); } .strength i.on.lv4 { background: var(--system-green); }
.strength span { font-size: 12px; color: var(--label-secondary); margin-left: 6px; }

.captcha-row { display: flex; gap: 10px; align-items: flex-start; }
.captcha-field { flex: 1; }
.captcha-box { flex: none; width: 112px; height: 50px; border: 1px solid var(--label-quaternary); border-radius: var(--radius-btn); background: #fff; padding: 0; overflow: hidden; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.captcha-box img { width: 100%; height: 100%; object-fit: cover; display: block; }
.captcha-hint { font-size: 12px; color: var(--system-blue); }

.opts { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 4px 2px 0; font-size: 13px; flex-wrap: wrap; }
.chk { display: inline-flex; align-items: center; gap: 6px; color: var(--label-secondary); cursor: pointer; }
.chk input { accent-color: var(--system-blue); }
.link { color: var(--system-blue); text-decoration: none; }
.muted { color: var(--label-tertiary); font-size: 12px; }

.server-error { margin-top: 12px; padding: 10px 12px; border-radius: 10px; background: rgba(255, 59, 48, 0.08); color: #C62A22; font-size: 13px; line-height: 1.5; }

.footer-hint { margin-top: 24px; font-size: var(--fs-caption-1); color: var(--label-secondary); text-align: center; }
.switch-link { color: var(--system-blue); cursor: pointer; margin-left: 4px; }

@media (max-width: 900px) {
  .login-page { grid-template-columns: 1fr; }
  .side { display: none; }
  .panel { align-items: flex-start; padding-top: 72px; }
}
</style>
