<template>
  <div class="app-layout">
    <!-- 顶部导航栏 -->
    <header class="top-header">
      <div class="header-left">
        <div class="logo">
          <span class="logo-text">AIGC--多模态检测</span>
        </div>
        <nav class="main-nav">
          <router-link
            v-for="item in navItems"
            :key="item.path"
            :to="item.path"
            class="nav-link"
            :class="{ active: route.path === item.path }"
          >
            {{ item.name }}
          </router-link>
        </nav>
      </div>
      <div class="header-right">
        <div class="quota-badge">
          配额: {{ auth.user?.quota_remaining ?? 1000 }}
        </div>
        <el-dropdown trigger="click">
          <div class="user-menu">
            <div class="user-avatar">{{ auth.user?.username?.charAt(0)?.toUpperCase() || 'U' }}</div>
            <span class="user-name">{{ auth.user?.username || '用户' }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/dashboard')">
                个人中心
              </el-dropdown-item>
              <el-dropdown-item @click="router.push('/history')">
                检测历史
              </el-dropdown-item>
              <el-dropdown-item v-if="auth.user?.role === 'admin'" @click="router.push('/admin')">
                管理后台
              </el-dropdown-item>
              <el-dropdown-item divided @click="auth.logout()">
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <keep-alive :max="10">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAuthStore } from "@/stores/auth"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { name: "首页", path: "/dashboard" },
  { name: "文本检测", path: "/detect/text" },
  { name: "图像检测", path: "/detect/image" },
  { name: "音频检测", path: "/detect/audio" },
  { name: "论文检测", path: "/detect/thesis" },
  { name: "降AIGC", path: "/detect/reduce" },
  { name: "AI助手", path: "/assistant" },
]

onMounted(() => {
  if (!auth.user) auth.fetchUser()
})
</script>

<style scoped>
.app-layout {
  min-height: 100vh;
  background: #f8fafc;
}

.top-header {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 72px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 40px;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 56px;
}

.logo {
  display: flex;
  align-items: center;
}

.logo-text {
  font-size: 24px;
  font-weight: 800;
  background: linear-gradient(135deg, #1a1a2e 0%, #667eea 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.5px;
}

.main-nav {
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-link {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  border-radius: 10px;
  color: #475569;
  font-size: 16px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.25s ease;
  letter-spacing: 0.3px;
}

.nav-link:hover {
  color: #667eea;
  background: rgba(102, 126, 234, 0.08);
}

.nav-link.active {
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.35);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.quota-badge {
  padding: 10px 20px;
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.12) 0%, rgba(118, 75, 162, 0.12) 100%);
  border-radius: 20px;
  color: #5b21b6;
  font-size: 15px;
  font-weight: 700;
}

.user-menu {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px 8px 8px;
  border-radius: 28px;
  background: #f1f5f9;
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-menu:hover {
  background: #e2e8f0;
}

.user-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 16px;
}

.user-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e293b;
}

.main-content {
  padding-top: 72px;
  min-height: 100vh;
}

@media (max-width: 1024px) {
  .main-nav {
    display: none;
  }

  .top-header {
    padding: 0 20px;
    height: 64px;
  }

  .main-content {
    padding-top: 64px;
  }
}
</style>
