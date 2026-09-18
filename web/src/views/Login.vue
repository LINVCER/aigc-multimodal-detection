<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')

async function onSubmit() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  try {
    await auth.login(username.value, password.value)
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch { /* 拦截器已 toast */ }
}
</script>

<template>
  <div class="login-page">
    <div class="wrap">
      <div class="hero">
        <div class="brand">论文AIGC检测</div>
        <div class="tagline">教育部 2026 新规 · 学位论文 AI 率检测</div>
      </div>

      <div class="form">
        <div class="field">
          <input v-model="username" placeholder="学号 / 工号" class="apple-input" @keyup.enter="onSubmit" />
        </div>
        <div class="field">
          <input v-model="password" type="password" placeholder="密码" class="apple-input" @keyup.enter="onSubmit" />
        </div>

        <el-button
          type="primary" round size="large"
          :loading="auth.loading" style="width: 100%; margin-top: 12px; height: 50px; font-size: 17px"
          @click="onSubmit"
        >登 录</el-button>

        <div class="footer-hint">首次使用请通过学校统一身份认证或联系管理员开通</div>
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

.field {
  background: rgba(120, 120, 128, 0.12);
  border-radius: var(--radius-btn);
  padding: 2px 16px;
  margin-bottom: 10px;
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
</style>
