<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import FeedbackDialog from '@/components/FeedbackDialog.vue'

const auth = useAuthStore()
const router = useRouter()

const feedbackOpen = ref(false)
const pwdOpen = ref(false)
const pwd = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdError = computed(() => {
  const p = pwd.value
  if (!p.oldPassword) return '请输入原密码'
  if (p.newPassword.length < 6 || p.newPassword.length > 32) return '新密码长度 6-32 位'
  if (!/[A-Za-z]/.test(p.newPassword) || !/[0-9]/.test(p.newPassword)) return '新密码需同时包含字母和数字'
  if (p.newPassword === p.oldPassword) return '新密码不能与原密码相同'
  if (p.confirmPassword !== p.newPassword) return '两次输入的新密码不一致'
  return ''
})
async function submitPassword() {
  if (pwdError.value) { ElMessage.warning(pwdError.value); return }
  try {
    await auth.changePassword(pwd.value.oldPassword, pwd.value.newPassword, pwd.value.confirmPassword)
    pwdOpen.value = false
    ElMessage.success('密码已修改，请重新登录')
    router.replace('/login')
  } catch { /* 拦截器已 toast */ }
}

const avatarLetter = computed(() => (auth.user?.realName || auth.user?.username || 'U').charAt(0).toUpperCase())

async function logout() {
  try {
    await ElMessageBox.confirm('确定要退出登录？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
    await auth.logout()
    router.replace('/login')
  } catch { /* 取消 */ }
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="title">我的</span>
        <span></span>
      </div>
    </el-header>

    <el-main class="main">
      <div class="wrap">
        <!-- Hero user card -->
        <el-card class="hero">
          <div class="hero-inner">
            <div class="avatar">{{ avatarLetter }}</div>
            <div class="user-info">
              <div class="name">{{ auth.user?.realName || auth.user?.username || '已登录用户' }}</div>
              <div class="sub">{{ auth.user?.role || 'STUDENT' }} · {{ auth.user?.orgName || '教育部合规检测' }}</div>
            </div>
          </div>
        </el-card>

        <!-- 账户 group -->
        <div class="group-label">账户</div>
        <el-card class="group-card" body-style="padding:0">
          <div class="row">
            <span class="row-title">用户名</span>
            <span class="row-value">{{ auth.user?.username || '—' }}</span>
          </div>
          <div class="separator"></div>
          <div class="row">
            <span class="row-title">额度余额</span>
            <span class="row-value muted">接入后端后展示</span>
          </div>
          <div class="separator"></div>
          <div class="row clickable" @click="router.push('/dashboard')">
            <span class="row-title">历史报告</span>
            <span class="chevron">›</span>
          </div>
          <div class="separator"></div>
          <div class="row clickable" @click="pwdOpen = true">
            <span class="row-title">修改密码</span>
            <span class="chevron">›</span>
          </div>
        </el-card>

        <!-- 关于 group -->
        <div class="group-label">关于</div>
        <el-card class="group-card" body-style="padding:0">
          <div class="row clickable" @click="feedbackOpen = true">
            <span class="row-title">意见反馈</span>
            <span class="chevron">›</span>
          </div>
          <div class="separator"></div>
          <div class="row clickable" @click="router.push('/privacy')">
            <span class="row-title">隐私政策</span>
            <span class="chevron">›</span>
          </div>
          <div class="separator"></div>
          <div class="row">
            <span class="row-title">版本</span>
            <span class="row-value muted">v0.1.0</span>
          </div>
        </el-card>

        <!-- Destructive -->
        <el-card class="group-card danger-card" body-style="padding:0" @click="logout">
          <div class="row danger">
            <span class="danger-text">退出登录</span>
          </div>
        </el-card>
      </div>
    </el-main>

    <FeedbackDialog v-model="feedbackOpen" default-category="suggestion" />

    <el-dialog v-model="pwdOpen" title="修改密码" width="420" align-center destroy-on-close>
      <el-form label-position="top" @submit.prevent="submitPassword">
        <el-form-item label="原密码"><el-input v-model="pwd.oldPassword" type="password" show-password autocomplete="current-password" /></el-form-item>
        <el-form-item label="新密码（6-32 位，含字母和数字）"><el-input v-model="pwd.newPassword" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-form-item label="确认新密码"><el-input v-model="pwd.confirmPassword" type="password" show-password autocomplete="new-password" /></el-form-item>
        <div class="pwd-hint">修改成功后所有设备需重新登录</div>
      </el-form>
      <template #footer>
        <el-button round @click="pwdOpen = false">取消</el-button>
        <el-button type="primary" round :loading="auth.loading" :disabled="!!pwdError" @click="submitPassword">确认修改</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header { background: var(--system-background); border-bottom: 1px solid var(--label-quaternary); padding: 0; }
.header-inner { height: 60px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }

.main { padding: 32px 24px; }
.wrap { max-width: 560px; margin: 0 auto; }

.hero-inner { display: flex; align-items: center; gap: 20px; }
.avatar {
  width: 64px; height: 64px; border-radius: 50%;
  background: linear-gradient(135deg, var(--system-blue) 0%, var(--system-teal) 100%);
  color: #fff; font-size: 28px; font-weight: var(--fw-semibold);
  display: flex; align-items: center; justify-content: center;
}
.name { font-size: 22px; font-weight: var(--fw-semibold); letter-spacing: -0.3px; color: var(--label); }
.sub  { font-size: var(--fs-subhead); color: var(--label-secondary); margin-top: 4px; }

.group-label {
  font-size: var(--fs-caption-1);
  font-weight: var(--fw-medium);
  color: var(--label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 24px 12px 8px;
}
.group-card { position: relative; }
.row {
  padding: 14px 20px;
  display: flex; justify-content: space-between; align-items: center;
  transition: background var(--dur-fast);
}
.row.clickable { cursor: pointer; }
.row.clickable:hover { background: rgba(60, 60, 67, 0.06); }
.row-title { font-size: var(--fs-body); color: var(--label); }
.row-value { font-size: var(--fs-body); color: var(--label); }
.row-value.muted { color: var(--label-secondary); }
.chevron { color: var(--label-tertiary); font-size: 22px; line-height: 1; }
.separator { height: 1px; background: var(--label-quaternary); margin-left: 20px; }

.danger-card { margin-top: 32px; cursor: pointer; }
.pwd-hint { font-size: 12px; color: var(--label-tertiary); }
.danger { justify-content: center; padding: 16px 20px; }
.danger-text { color: var(--system-red); font-size: var(--fs-body); font-weight: var(--fw-medium); }
</style>
