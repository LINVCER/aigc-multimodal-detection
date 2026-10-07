<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { getCaptcha } from '@/api/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const captchaId = ref('')
const captchaCode = ref('')
const captchaImg = ref('')

async function loadCaptcha() {
  try {
    const c = await getCaptcha()
    captchaId.value = c.captchaId
    captchaImg.value = c.imageBase64
  } catch {
    captchaId.value = ''
    captchaImg.value = ''
  }
}
onMounted(loadCaptcha)

async function onSubmit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  if (mode.value === 'register' && password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  try {
    if (mode.value === 'register') {
      await auth.register(username.value, password.value, confirmPassword.value, captchaId.value, captchaCode.value)
      ElMessage.success('注册成功，已自动登录')
    } else {
      await auth.login(username.value, password.value, captchaId.value, captchaCode.value)
    }
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch {
    // 验证码错误/失效时刷新验证码
    if (captchaId.value) loadCaptcha()
    captchaCode.value = ''
  }
}
</script>

<template>
  <div class="login-page">
    <div class="wrap">
      <div class="hero">
        <div class="brand">知源</div>
        <div class="tagline">看得懂的论文 AI 率检测 · 溯源 · 不代写</div>
      </div>

      <div class="seg">
        <button class="seg-btn" :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button class="seg-btn" :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <div class="form">
        <div class="field">
          <input v-model="username" placeholder="学号 / 工号 / 邮箱" class="apple-input" @keyup.enter="onSubmit" />
        </div>
        <div class="field">
          <input v-model="password" type="password" placeholder="密码（6-32 位）" class="apple-input" @keyup.enter="onSubmit" />
        </div>
        <div v-if="mode === 'register'" class="field">
          <input v-model="confirmPassword" type="password" placeholder="再次输入密码" class="apple-input" @keyup.enter="onSubmit" />
        </div>

        <div class="captcha-row">
          <div class="field captcha-field">
            <input v-model="captchaCode" placeholder="验证码" class="apple-input" @keyup.enter="onSubmit" />
          </div>
          <img v-if="captchaImg" :src="captchaImg" class="captcha-img" alt="验证码" title="点击刷新" @click="loadCaptcha" />
        </div>

        <el-button
          type="primary" round size="large"
          :loading="auth.loading" style="width: 100%; margin-top: 12px; height: 50px; font-size: 17px"
          @click="onSubmit"
        >{{ mode === 'login' ? '登 录' : '注册并登录' }}</el-button>

        <div class="footer-hint">
          {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
          <span class="switch-link" @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '立即注册' : '去登录' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  background: var(--system-background);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.wrap { width: 100%; max-width: 380px; }

.hero { margin-bottom: 48px; }
.brand {
  font-size: var(--fs-large-title);
  font-weight: var(--fw-bold);
  letter-spacing: -0.8px;
  color: var(--label);
  line-height: 1.1;
}
.tagline {
  font-size: var(--fs-subhead);
  color: var(--label-secondary);
  margin-top: 8px;
}

.seg {
  display: flex;
  background: rgba(120, 120, 128, 0.12);
  border-radius: var(--radius-btn);
  padding: 3px;
  margin-bottom: 16px;
}
.seg-btn {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--label);
  font-size: var(--fs-subhead);
  font-weight: var(--fw-medium);
  padding: 8px 0;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
  transition: background-color var(--dur-fast);
}
.seg-btn.active {
  background: #fff;
  font-weight: var(--fw-semibold);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.field {
  background: rgba(120, 120, 128, 0.12);
  border-radius: var(--radius-btn);
  padding: 2px 16px;
  margin-bottom: 10px;
}
.captcha-row { display: flex; gap: 10px; align-items: center; }
.captcha-field { flex: 1; margin-bottom: 10px; }
.captcha-img {
  height: 46px; width: 108px; border-radius: var(--radius-btn);
  cursor: pointer; object-fit: cover; margin-bottom: 10px;
}
.apple-input {
  width: 100%;
  height: 46px;
  border: none;
  background: transparent;
  outline: none;
  font-size: var(--fs-body);
  color: var(--label);
  font-family: inherit;
}
.apple-input::placeholder { color: var(--label-tertiary); }

.footer-hint {
  margin-top: 24px;
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
  text-align: center;
}
.switch-link { color: var(--system-blue); cursor: pointer; margin-left: 4px; }
</style>
