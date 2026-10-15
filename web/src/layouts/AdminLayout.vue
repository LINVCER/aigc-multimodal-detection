<script setup lang="ts">
import ZyIcon from '@/components/ZyIcon.vue'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { getFeedbackStats } from '@/api/feedback'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/admin/dashboard', icon: 'chart', text: '运营大盘' },
  { path: '/admin/users',     icon: 'user', text: '用户管理' },
  { path: '/admin/tasks',     icon: 'file-text', text: '任务列表' },
  { path: '/admin/feedback',  icon: 'chat', text: '用户反馈' },
  { path: '/admin/assistant', icon: 'xiaobai-spark', text: '助手运营' },
  { path: '/admin/analytics', icon: 'trend', text: '检测分析' },
  { path: '/admin/schools',   icon: 'graduation', text: '院校数据' },
  { path: '/admin/config',    icon: 'tool', text: '参数配置' },
]
const activePath = computed(() => route.path)

/* 侧栏角标：待处理反馈数（进后台时拉一次，处理完回到列表时由页面自己刷新 KPI） */
const pendingFeedback = ref(0)
onMounted(async () => { try { pendingFeedback.value = (await getFeedbackStats()).byStatus?.PENDING || 0 } catch { pendingFeedback.value = 0 } })

async function logout() {
  await auth.logout()
  router.replace('/login')
}
</script>

<template>
  <el-container class="admin-shell">
    <el-aside class="side" width="220px">
      <div class="brand">
        <img src="/logo-mark.png" alt="" class="brand-logo" />
        <span class="brand-text">知源 · 运营后台</span>
      </div>
      <el-menu :default-active="activePath" router class="menu" background-color="transparent">
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <ZyIcon class="menu-icon" :name="m.icon" :size="18" />
          <span>{{ m.text }}</span>
          <span v-if="m.path === '/admin/feedback' && pendingFeedback" class="badge">{{ pendingFeedback > 99 ? '99+' : pendingFeedback }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="top">
        <div class="crumb">{{ menus.find(m => m.path === activePath)?.text || '' }}</div>
        <div class="user">
          <span class="user-name">{{ auth.user?.realName || auth.user?.username || 'OPS' }}</span>
          <el-button link type="danger" @click="logout"><ZyIcon name="logout" :size="15" />退出</el-button>
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
  background: var(--system-background);
  color: var(--label);
  padding: 0;
  border-right: 1px solid var(--separator);
}
.brand {
  height: 60px;
  display: flex; align-items: center;
  padding: 0 20px;
  font-weight: 600;
  gap: 10px;
  border-bottom: 1px solid var(--separator);
}
.brand-logo { width: 26px; height: 26px; object-fit: contain; }
.badge { margin-left: auto; min-width: 18px; height: 18px; padding: 0 6px; border-radius: 9px; background: var(--accent-orange); color: #fff; font-size: 11px; font-weight: 600; line-height: 18px; text-align: center; }
.brand-text { font-size: 16px; letter-spacing: 0.4px; }
.menu {
  border-right: 0;
}
:deep(.el-menu-item) {
  color: var(--label-secondary) !important;
  height: 42px; line-height: 42px;
  border-radius: 10px;
  margin: 4px 12px;
  display: flex; align-items: center;
}
:deep(.el-menu-item:hover) {
  background: var(--bg-deep) !important;
  color: var(--label) !important;
}
:deep(.el-menu-item.is-active) {
  background: var(--ai-700) !important;
  color: #FFFFFF !important;
  font-weight: 600;
}
.menu-icon { margin-right: 10px; }

.top {
  height: 60px;
  background: #FFFFFF;
  border-bottom: 1px solid var(--separator);
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 24px;
}
.crumb { font-size: 16px; font-weight: 600; color: var(--label); }
.user { display: flex; align-items: center; gap: 16px; }
.user-name { font-size: 14px; color: var(--label-secondary); }

.main {
  background: var(--system-grouped-background);
  padding: 24px;
}
</style>
