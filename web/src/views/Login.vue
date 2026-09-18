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
  } catch (e: any) {
    // 拦截器已 toast 具体错误
  }
}
</script>

<template>
  <div class="login-page">
    <div class="card">
      <h1 class="title">论文 AIGC 检测</h1>
      <p class="subtitle">教育部 2026 新规 · 学位论文 AI 率检测</p>

      <el-form @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="username" placeholder="学号 / 工号" size="large" clearable />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" placeholder="密码" type="password" size="large" show-password @keyup.enter="onSubmit" />
        </el-form-item>
        <el-button
          type="primary" size="large" native-type="submit"
          :loading="auth.loading" style="width: 100%"
          @click="onSubmit"
        >登 录</el-button>
      </el-form>

      <p class="hint">首次使用请通过学校统一身份认证或联系管理员开通</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a56db 0%, #3b82f6 100%);
}
.card {
  width: 440px;
  padding: 48px 40px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 12px 32px rgba(17, 24, 39, 0.15);
}
.title { text-align: center; color: #1a56db; margin: 0; font-size: 24px; }
.subtitle { text-align: center; color: #6b7280; font-size: 13px; margin: 8px 0 32px; }
.hint { text-align: center; color: #9ca3af; font-size: 12px; margin: 24px 0 0; }
</style>
