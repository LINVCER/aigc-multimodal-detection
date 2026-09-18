<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

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
          <div class="row clickable">
            <span class="row-title">历史报告</span>
            <span class="chevron">›</span>
          </div>
        </el-card>

        <!-- 关于 group -->
        <div class="group-label">关于</div>
        <el-card class="group-card" body-style="padding:0">
          <div class="row clickable">
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
.danger { justify-content: center; padding: 16px 20px; }
.danger-text { color: var(--system-red); font-size: var(--fs-body); font-weight: var(--fw-medium); }
</style>
