<template>
  <div class="dashboard-page">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-content">
        <div class="welcome-text">
          <h1>
            <span class="greeting">{{ greeting }}</span>
            <span class="username">{{ auth.user?.username || '用户' }}</span>
          </h1>
          <p class="welcome-desc">今天想检测什么内容？</p>
        </div>
        <div class="welcome-stats">
          <div class="quick-stat">
            <span class="stat-number">{{ store.cache.length }}</span>
            <span class="stat-label">累计检测</span>
          </div>
          <div class="quick-stat">
            <span class="stat-number">{{ aiCount }}</span>
            <span class="stat-label">AI检出</span>
          </div>
          <div class="quick-stat">
            <span class="stat-number">{{ humanCount }}</span>
            <span class="stat-label">人工作品</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 检测入口卡片 -->
    <div class="modules-section">
      <h2 class="section-title">快速检测</h2>
      <div class="modules-grid">
        <div
          v-for="m in modules"
          :key="m.path"
          class="module-card"
          @click="router.push(m.path)"
        >
          <div class="card-bg" :style="{ background: m.gradient }"></div>
          <div class="card-icon" :style="{ background: m.iconBg }">
            <span class="card-emoji">{{ m.emoji }}</span>
          </div>
          <div class="card-content">
            <h3>{{ m.name }}</h3>
            <p>{{ m.desc }}</p>
          </div>
          <div class="card-arrow">&rarr;</div>
        </div>
      </div>
    </div>

    <!-- 历史记录 -->
    <div class="history-section" v-if="store.cache.length > 0">
      <div class="history-header">
        <h2 class="section-title">最近检测</h2>
        <el-button link class="view-all-btn" @click="router.push('/history')">
          查看全部 &rarr;
        </el-button>
      </div>
      <div class="history-list">
        <div
          v-for="r in recentRecords"
          :key="r.id"
          class="history-item"
          @click="navigateTo(r)"
        >
          <div class="item-left">
            <div class="item-icon" :class="r.type">
              <span class="type-label">{{ r.type === 'text' ? '文' : r.type === 'image' ? '图' : r.type === 'audio' ? '音' : '论' }}</span>
            </div>
            <div class="item-info">
              <span class="item-title">{{ r.title }}</span>
              <span class="item-time">{{ r.timestamp }}</span>
            </div>
          </div>
          <div class="item-right">
            <div class="item-result" :class="getResultClass(r)">
              <span class="result-dot" :class="getResultClass(r)"></span>
              <span class="result-text">{{ getResultText(r) }}</span>
            </div>
            <span class="item-confidence" :style="{ color: getConfidenceColor(r) }">
              {{ getConfidence(r) }}%
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div class="empty-section" v-else>
      <div class="empty-content">
        <h3>开始您的第一次检测</h3>
        <p>选择上方的检测类型，快速识别 AI 生成内容</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { useResultsStore } from "@/stores/results"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const store = useResultsStore()
const auth = useAuthStore()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return "夜深了"
  if (hour < 12) return "早上好"
  if (hour < 14) return "中午好"
  if (hour < 18) return "下午好"
  return "晚上好"
})

const aiCount = computed(() =>
  store.cache.filter(r => r.data?.is_ai_generated || r.data?.overall_score?.is_ai_generated).length
)

const humanCount = computed(() =>
  store.cache.filter(r => r.data?.is_ai_generated === false || r.data?.overall_score?.is_ai_generated === false).length
)

const recentRecords = computed(() => store.cache.slice().reverse().slice(0, 10))

const modules = [
  {
    name: "文本检测",
    desc: "识别 AI 生成的文本内容",
    path: "/detect/text",
    emoji: "T",
    gradient: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    iconBg: "rgba(102, 126, 234, 0.1)"
  },
  {
    name: "图像检测",
    desc: "检测 AI 生成的图片",
    path: "/detect/image",
    emoji: "I",
    gradient: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
    iconBg: "rgba(16, 185, 129, 0.1)"
  },
  {
    name: "音频检测",
    desc: "识别合成语音",
    path: "/detect/audio",
    emoji: "A",
    gradient: "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
    iconBg: "rgba(245, 158, 11, 0.1)"
  },
  {
    name: "论文检测",
    desc: "论文 AIGC 整体分析",
    path: "/detect/thesis",
    emoji: "P",
    gradient: "linear-gradient(135deg, #dc2626 0%, #b91c1c 100%)",
    iconBg: "rgba(220, 38, 38, 0.1)"
  },
  {
    name: "降AIGC",
    desc: "一键降低论文 AI 检测率",
    path: "/detect/reduce",
    emoji: "D",
    gradient: "linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)",
    iconBg: "rgba(139, 92, 246, 0.1)"
  },
  {
    name: "AI助手",
    desc: "智能写作辅助工具",
    path: "/assistant",
    emoji: "?",
    gradient: "linear-gradient(135deg, #ec4899 0%, #be185d 100%)",
    iconBg: "rgba(236, 72, 153, 0.1)"
  },
]

function getResultClass(r: any): string {
  if (r.data?.is_ai_generated || r.data?.overall_score?.is_ai_generated) return 'ai'
  return 'human'
}

function getResultText(r: any): string {
  if (r.data?.is_ai_generated || r.data?.overall_score?.is_ai_generated) return 'AI生成'
  return '真人'
}

function getConfidence(r: any): string {
  if (r.data?.confidence) return (r.data.confidence * 100).toFixed(0)
  if (r.data?.overall_score?.ai_rate) return r.data.overall_score.ai_rate.toString()
  return '0'
}

function getConfidenceColor(r: any): string {
  const conf = parseFloat(getConfidence(r)) / 100
  if (r.data?.is_ai_generated || r.data?.overall_score?.is_ai_generated) {
    if (conf > 0.7) return '#dc2626'
    if (conf > 0.4) return '#f59e0b'
    return '#10b981'
  }
  return '#10b981'
}

function navigateTo(r: any) {
  const routes: Record<string, string> = {
    text: "/detect/text", image: "/detect/image", thesis: "/detect/thesis",
  }
  router.push(routes[r.type] || "/detect/text")
}
</script>

<style scoped>
.dashboard-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px;
}

.welcome-section {
  margin-bottom: 40px;
}

.welcome-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
  padding: 40px;
  color: white;
  position: relative;
  overflow: hidden;
}

.welcome-content::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -20%;
  width: 400px;
  height: 400px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 50%;
}

.welcome-content::after {
  content: '';
  position: absolute;
  bottom: -30%;
  right: 10%;
  width: 200px;
  height: 200px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 50%;
}

.welcome-text {
  position: relative;
  z-index: 1;
}

.welcome-text h1 {
  margin: 0 0 8px 0;
  font-size: 32px;
  font-weight: 700;
}

.greeting {
  opacity: 0.9;
}

.username {
  margin-left: 8px;
}

.welcome-desc {
  margin: 0;
  font-size: 16px;
  opacity: 0.8;
}

.welcome-stats {
  display: flex;
  gap: 32px;
  position: relative;
  z-index: 1;
}

.quick-stat {
  text-align: center;
}

.stat-number {
  display: block;
  font-size: 36px;
  font-weight: 700;
  line-height: 1;
}

.stat-label {
  font-size: 14px;
  opacity: 0.8;
  margin-top: 4px;
}

.modules-section {
  margin-bottom: 40px;
}

.section-title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0 0 24px 0;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.module-card {
  background: white;
  border-radius: 16px;
  padding: 28px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  transition: all 0.3s ease;
}

.module-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
}

.card-bg {
  position: absolute;
  top: 0;
  right: 0;
  width: 100px;
  height: 100px;
  border-radius: 50%;
  opacity: 0.08;
  transform: translate(30%, -30%);
}

.card-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.card-emoji {
  font-size: 22px;
  font-weight: 800;
  color: #667eea;
}

.card-content h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 6px 0;
}

.card-content p {
  font-size: 13px;
  color: #64748b;
  margin: 0;
}

.card-arrow {
  position: absolute;
  top: 24px;
  right: 24px;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transform: translateX(-8px);
  transition: all 0.3s ease;
  font-size: 18px;
  color: #667eea;
  font-weight: 700;
}

.module-card:hover .card-arrow {
  opacity: 1;
  transform: translateX(0);
}

.history-section {
  background: white;
  border-radius: 16px;
  padding: 28px;
  border: 1px solid #e2e8f0;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.view-all-btn {
  color: #667eea;
  font-weight: 600;
  font-size: 15px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: #f8fafc;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  border: 1px solid transparent;
}

.history-item:hover {
  background: white;
  border-color: #e2e8f0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.item-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.item-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.item-icon.text {
  background: rgba(102, 126, 234, 0.1);
  color: #667eea;
}

.item-icon.image {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.item-icon.audio {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
}

.item-icon.thesis {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.type-label {
  font-size: 15px;
  font-weight: 700;
}

.item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-title {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
}

.item-time {
  font-size: 12px;
  color: #94a3b8;
}

.item-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.item-result {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
}

.item-result.ai {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}

.item-result.human {
  background: rgba(16, 185, 129, 0.1);
  color: #10b981;
}

.result-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.result-dot.ai {
  background: #dc2626;
}

.result-dot.human {
  background: #10b981;
}

.item-confidence {
  font-size: 14px;
  font-weight: 600;
  min-width: 50px;
  text-align: right;
}

.empty-section {
  background: white;
  border-radius: 16px;
  padding: 60px 40px;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.empty-content h3 {
  font-size: 20px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px 0;
}

.empty-content p {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

@media (max-width: 1024px) {
  .modules-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .welcome-content {
    flex-direction: column;
    align-items: flex-start;
    gap: 24px;
  }

  .welcome-stats {
    width: 100%;
    justify-content: space-around;
  }
}

@media (max-width: 640px) {
  .dashboard-page {
    padding: 16px;
  }

  .modules-grid {
    grid-template-columns: 1fr;
  }

  .welcome-content {
    padding: 24px;
  }

  .welcome-text h1 {
    font-size: 24px;
  }

  .history-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .item-right {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
