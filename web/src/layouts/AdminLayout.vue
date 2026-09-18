<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/admin/dashboard', icon: '📊', text: '运营大盘' },
  { path: '/admin/users',     icon: '👤', text: '用户管理' },
  { path: '/admin/tasks',     icon: '📄', text: '任务列表' },
  { path: '/admin/feedback',  icon: '💬', text: '用户反馈' },
]
const activePath = computed(() => route.path)

async function logout() {
  await auth.logout()
  router.replace('/login')
}
</script>

<template>
  <el-container class="admin-shell">
    <el-aside class="side" width="220px">
      <div class="brand">
        <span class="brand-mark">🎯</span>
        <span class="brand-text">运营后台</span>
      </div>
      <el-menu :default-active="activePath" router class="menu" background-color="transparent">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <span class="menu-icon">{{ m.icon }}</span>
          <span>{{ m.text }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="top">
        <div class="crumb">{{ menus.find(m => m.path === activePath)?.text || '' }}</div>
        <div class="user">
          <span class="user-name">{{ auth.user?.realName || auth.user?.username || 'OPS' }}</span>
          <el-button link @click="router.push('/dashboard')">← 返回 C 端</el-button>
          <el-button link type="danger" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-shell { height: 100vh; }
.side {
  background: #1E1E22;
  color: #FFFFFF;
  padding: 0;
}
.brand {
  height: 60px;
  display: flex; align-items: center;
  padding: 0 20px;
  font-weight: 600;
  gap: 10px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
}
.brand-mark { font-size: 22px; }
.brand-text { font-size: 16px; letter-spacing: 0.4px; }
.menu {
  border-right: 0;
}
:deep(.el-menu-item) {
  color: rgba(255,255,255,0.72) !important;
  height: 46px; line-height: 46px;
  border-radius: 8px;
  margin: 4px 12px;
}
:deep(.el-menu-item:hover) {
  background: rgba(255,255,255,0.08) !important;
  color: #FFFFFF !important;
}
:deep(.el-menu-item.is-active) {
  background: rgba(0,122,255,0.24) !important;
  color: #FFFFFF !important;
}
.menu-icon { margin-right: 10px; font-size: 16px; }

.top {
  height: 60px;
  background: #FFFFFF;
  border-bottom: 1px solid rgba(60,60,67,0.18);
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 24px;
}
.crumb { font-size: 16px; font-weight: 600; color: #1C1C1E; }
.user { display: flex; align-items: center; gap: 16px; }
.user-name { font-size: 14px; color: rgba(60,60,67,0.60); }

.main {
  background: #F2F2F7;
  padding: 24px;
}
</style>
