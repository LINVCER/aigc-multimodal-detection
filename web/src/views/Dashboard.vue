<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listTasks, deleteTask, retryTask, getStatistics } from '@/api/detect'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/EmptyState.vue'
import Skeleton from '@/components/Skeleton.vue'
import type { DetectTask, StatisticsResp } from '@/api/types'

const router = useRouter()
const auth = useAuthStore()

const tasks = ref<DetectTask[]>([])
const total = ref(0)
const loading = ref(false)
const firstLoad = ref(true)
const error = ref('')
const keyword = ref('')
const statusFilter = ref('')

// Dashboard 统计（Wave 2.c）
const stats = ref<StatisticsResp | null>(null)
async function loadStats() {
  try { stats.value = await getStatistics() } catch { /* 静默：拦截器已 toast */ }
}

// 折线：把 dailyTrend 转成 SVG 路径。图 W=560 H=120，左右各留 4px padding
const trendChart = computed(() => {
  const s = stats.value
  if (!s || !s.dailyTrend || s.dailyTrend.length === 0) return null

  const W = 560, H = 120, PAD = 4
  const pts = s.dailyTrend
  const maxCount = Math.max(1, ...pts.map(p => p.count))
  // 双 y 轴：折线（count）占主坐标，AI 率线用同一坐标系映射到 0-100

  const barW = (W - PAD * 2) / pts.length
  const stepX = (W - PAD * 2 - barW) / Math.max(pts.length - 1, 1)

  // 折线路径（当日检测量）
  let countPath = ''
  const countPts: { x: number; y: number; count: number; date: string }[] = []
  pts.forEach((p, i) => {
    const x = PAD + barW / 2 + i * stepX
    const y = H - PAD - (p.count / maxCount) * (H - PAD * 2)
    countPts.push({ x, y, count: p.count, date: p.date })
    countPath += (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1) + ' '
  })

  // 面积填充路径（同 count 折线 + 底部收口）
  let areaPath = countPath.replace(/^M/, 'M') +
    'L' + countPts[countPts.length - 1].x.toFixed(1) + ',' + (H - PAD) +
    'L' + countPts[0].x.toFixed(1) + ',' + (H - PAD) + ' Z'

  // AI 率折线（0-100 → H 内映射）
  let rateSegments: string[] = []
  let seg = ''
  const ratePts: { x: number; y: number; rate: number; date: string }[] = []
  pts.forEach((p, i) => {
    if (p.avgRate == null) {
      if (seg) { rateSegments.push(seg); seg = '' }
      return
    }
    const x = PAD + barW / 2 + i * stepX
    const y = H - PAD - (p.avgRate / 100) * (H - PAD * 2)
    ratePts.push({ x, y, rate: p.avgRate, date: p.date })
    seg += (seg === '' ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1) + ' '
  })
  if (seg) rateSegments.push(seg)

  return { W, H, countPath, areaPath, countPts, ratePts, rateSegments, maxCount }
})

let pollTimer: any = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listTasks({
      pageNum: 1, pageSize: 50,
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
    })
    tasks.value = data.rows
    total.value = data.total
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
    firstLoad.value = false
  }
}

const hasRunning = computed(() => tasks.value.some(t => t.status === 'PENDING' || t.status === 'RUNNING'))

function ensurePolling() {
  if (pollTimer || !hasRunning.value) return
  pollTimer = setInterval(async () => {
    await load()
    if (!hasRunning.value) stopPolling()
  }, 4000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

onMounted(async () => {
  // 并发拉列表与统计，首屏尽快出
  await Promise.all([load(), loadStats()])
  ensurePolling()
})
onUnmounted(stopPolling)

function aiRateColor(rate: number | null, threshold: number): string {
  if (rate == null) return 'var(--label-tertiary)'
  if (rate <= threshold) return 'var(--system-green)'
  if (rate <= threshold * 1.5) return 'var(--system-orange)'
  return 'var(--system-red)'
}

const STATUS_TAG = {
  PENDING: { type: 'info',    text: '排队中' },
  RUNNING: { type: 'warning', text: '检测中' },
  DONE:    { type: 'success', text: '已完成' },
  FAILED:  { type: 'danger',  text: '失败' },
} as const

const DEGREE_LABEL = { BACHELOR: '本科', MASTER: '硕士', PHD: '博士' } as const

const avatarLetter = computed(() =>
  (auth.user?.realName || auth.user?.username || 'U').charAt(0).toUpperCase())

function goDetail(id: number) { router.push({ name: 'TaskDetail', params: { id } }) }

async function onRetry(id: number) {
  await retryTask(id)
  ElMessage.success('已重新提交')
  await load(); ensurePolling()
}

async function onDelete(id: number) {
  await ElMessageBox.confirm('确认删除该检测记录？', '提示', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    confirmButtonClass: 'el-button--danger',
  })
  await deleteTask(id)
  ElMessage.success('已删除')
  await load()
}

const showEmpty = computed(() =>
  !loading.value && !error.value && tasks.value.length === 0)
const showEmptyFiltered = computed(() =>
  showEmpty.value && (keyword.value || statusFilter.value))
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <div class="brand-block">
          <span class="brand">论文AIGC检测</span>
        </div>
        <div class="header-actions">
          <div class="avatar-btn" @click="router.push('/profile')" :title="auth.user?.username || '我的'">
            {{ avatarLetter }}
          </div>
        </div>
      </div>
    </el-header>

    <el-main class="main">
      <div class="wrap">
        <!-- Large Title -->
        <div class="large-title-bar">
          <h1 class="large-title">检测记录</h1>
          <el-button type="primary" round size="large" @click="router.push('/upload')">+ 提交检测</el-button>
        </div>

        <!-- Stats overview (Wave 2.c) -->
        <div v-if="stats" class="stats-grid">
          <div class="stat-card">
            <div class="stat-label">今日</div>
            <div class="stat-value">{{ stats.today }}</div>
            <div class="stat-hint">篇检测</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">本月</div>
            <div class="stat-value">{{ stats.thisMonth }}</div>
            <div class="stat-hint">篇检测</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">平均 AI 率</div>
            <div class="stat-value">
              <template v-if="stats.avgAiRate != null">
                {{ stats.avgAiRate.toFixed(1) }}<span class="stat-value-unit">%</span>
              </template>
              <template v-else>—</template>
            </div>
            <div class="stat-hint">已完成任务</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">达标率</div>
            <div class="stat-value" :style="{ color: (stats.passRate ?? 0) >= 60 ? 'var(--system-green)' : (stats.passRate ?? 0) >= 30 ? 'var(--system-orange)' : 'var(--system-red)' }">
              <template v-if="stats.passRate != null">
                {{ stats.passRate.toFixed(0) }}<span class="stat-value-unit">%</span>
              </template>
              <template v-else>—</template>
            </div>
            <div class="stat-hint">低于红线比例</div>
          </div>
        </div>

        <!-- 30 天趋势折线（SVG 手绘，避免引 echarts） -->
        <el-card v-if="trendChart" class="trend-card" body-style="padding: 20px 24px">
          <div class="trend-header">
            <div class="trend-title">近 30 天趋势</div>
            <div class="trend-legend">
              <span><span class="legend-dot count"></span> 检测量</span>
              <span><span class="legend-dot rate"></span> 平均 AI 率</span>
            </div>
          </div>
          <svg :viewBox="`0 0 ${trendChart.W} ${trendChart.H}`" class="trend-svg">
            <!-- 网格：3 条水平参考线 -->
            <line v-for="y in [0.25, 0.5, 0.75]" :key="y"
              :x1="4" :y1="trendChart.H * y" :x2="trendChart.W - 4" :y2="trendChart.H * y"
              stroke="rgba(60,60,67,0.10)" stroke-width="1" stroke-dasharray="3 4"/>
            <!-- 检测量：淡蓝面积 + 蓝线 -->
            <path :d="trendChart.areaPath" fill="rgba(0,122,255,0.10)" />
            <path :d="trendChart.countPath" fill="none" stroke="var(--system-blue)" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>
            <circle v-for="p in trendChart.countPts" :key="'c-' + p.date"
              :cx="p.x" :cy="p.y" r="2.4" fill="var(--system-blue)"/>
            <!-- AI 率：橙色，虚线段（缺失日不连） -->
            <path v-for="(seg, i) in trendChart.rateSegments" :key="'r-' + i"
              :d="seg" fill="none" stroke="var(--system-orange)" stroke-width="1.6"
              stroke-linejoin="round" stroke-linecap="round"/>
            <circle v-for="p in trendChart.ratePts" :key="'rp-' + p.date"
              :cx="p.x" :cy="p.y" r="2.2" fill="var(--system-orange)"/>
          </svg>
          <div class="trend-axis">
            <span>{{ trendChart.countPts[0]?.date }}</span>
            <span>{{ trendChart.countPts[Math.floor(trendChart.countPts.length / 2)]?.date }}</span>
            <span>今天</span>
          </div>
        </el-card>

        <!-- Toolbar -->
        <div class="toolbar">
          <el-input v-model="keyword" placeholder="搜索论文标题" clearable @change="load" style="width: 300px" />
          <el-select v-model="statusFilter" placeholder="全部状态" clearable @change="load" style="width: 160px">
            <el-option label="进行中" value="RUNNING" />
            <el-option label="已完成" value="DONE" />
            <el-option label="失败" value="FAILED" />
          </el-select>
        </div>

        <!-- 首次加载：骨架 -->
        <Skeleton v-if="loading && firstLoad" :rows="4" />

        <!-- 错误 -->
        <EmptyState
          v-else-if="error && tasks.length === 0"
          icon="⚠️" :title="error" desc="下拉刷新或检查网络后重试"
          action-text="重新加载" @action="load"
        />

        <!-- 空（无搜索）-->
        <EmptyState
          v-else-if="showEmpty && !showEmptyFiltered"
          icon="📭" title="还没有检测记录"
          desc="上传你的论文，几十秒内拿到 AI 率报告"
          action-text="去上传" @action="router.push('/upload')"
        />

        <!-- 空（有搜索无匹配）-->
        <EmptyState
          v-else-if="showEmptyFiltered"
          icon="🔎" title="没有匹配的记录" desc="换个关键词或清空筛选"
        />

        <!-- 表格 -->
        <el-card v-else class="table-card" body-style="padding:0">
          <el-table :data="tasks" v-loading="loading && !firstLoad" style="width: 100%">
            <el-table-column prop="paperTitle" label="论文标题" min-width="360" show-overflow-tooltip>
              <template #default="{ row }">
                <a class="title-link" @click="goDetail(row.id)">{{ row.paperTitle }}</a>
              </template>
            </el-table-column>
            <el-table-column label="学位" width="80">
              <template #default="{ row }">
                <span class="degree-tag">{{ DEGREE_LABEL[row.degreeType as keyof typeof DEGREE_LABEL] || row.degreeType }}</span>
              </template>
            </el-table-column>
            <el-table-column label="红线" width="70" align="center">
              <template #default="{ row }">{{ row.threshold }}%</template>
            </el-table-column>
            <el-table-column label="AI 率" width="110" align="right">
              <template #default="{ row }">
                <span v-if="row.aiRate == null" style="color: var(--label-tertiary)">—</span>
                <span v-else class="rate" :style="{ color: aiRateColor(row.aiRate, row.threshold) }">
                  {{ row.aiRate.toFixed(1) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="(STATUS_TAG[row.status as keyof typeof STATUS_TAG] || STATUS_TAG.PENDING).type" size="small">
                  {{ (STATUS_TAG[row.status as keyof typeof STATUS_TAG] || STATUS_TAG.PENDING).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="createdAt" label="提交时间" width="180" />
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="goDetail(row.id)">查看</el-button>
                <el-button v-if="row.status === 'FAILED'" link @click="onRetry(row.id)">重试</el-button>
                <el-button link type="danger" @click="onDelete(row.id)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--system-grouped-background); }

.header {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--label-quaternary);
  padding: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-inner {
  height: 56px; padding: 0 24px; display: flex;
  justify-content: space-between; align-items: center;
}
.brand-block { display: flex; align-items: center; gap: 12px; }
.brand { font-size: var(--fs-headline); font-weight: var(--fw-semibold); color: var(--label); letter-spacing: -0.2px; }

.header-actions { display: flex; align-items: center; gap: 12px; }
.avatar-btn {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, var(--system-blue) 0%, var(--system-teal) 100%);
  color: #fff; font-size: 14px; font-weight: var(--fw-semibold);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: transform var(--dur-fast) var(--ease-standard);
}
.avatar-btn:hover  { transform: scale(1.06); }
.avatar-btn:active { transform: scale(0.94); }

.main { padding: 32px 24px 48px; }
.wrap { max-width: 1200px; margin: 0 auto; }

.large-title-bar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
}
.large-title {
  font-size: var(--fs-large-title);
  font-weight: var(--fw-bold);
  letter-spacing: -0.8px;
  margin: 0;
}

.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }

/* ============ 统计面板（Wave 2.c） ============ */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: var(--system-background);
  border-radius: var(--radius-card);
  padding: 20px 22px;
  box-shadow: var(--shadow-card);
}
.stat-label {
  font-size: var(--fs-caption-1);
  font-weight: var(--fw-medium);
  color: var(--label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}
.stat-value {
  font-size: 34px;
  font-weight: var(--fw-bold);
  letter-spacing: -0.8px;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
  color: var(--label);
}
.stat-value-unit { font-size: 16px; font-weight: var(--fw-semibold); color: var(--label-secondary); margin-left: 2px; }
.stat-hint { margin-top: 4px; font-size: var(--fs-caption-1); color: var(--label-secondary); }

/* 折线卡 */
.trend-card { margin-bottom: 20px; }
.trend-header {
  display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: 12px;
}
.trend-title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); color: var(--label); }
.trend-legend {
  display: flex; gap: 16px;
  font-size: var(--fs-caption-1); color: var(--label-secondary);
}
.legend-dot {
  display: inline-block;
  width: 8px; height: 8px; border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
.legend-dot.count { background: var(--system-blue); }
.legend-dot.rate  { background: var(--system-orange); }
.trend-svg {
  width: 100%;
  height: 120px;
  display: block;
}
.trend-axis {
  display: flex; justify-content: space-between;
  margin-top: 4px;
  font-size: var(--fs-caption-2);
  color: var(--label-tertiary);
  font-variant-numeric: tabular-nums;
}

.title-link { color: var(--system-blue); cursor: pointer; }
.title-link:hover { text-decoration: underline; }

.degree-tag {
  background: rgba(0, 122, 255, 0.10);
  color: var(--system-blue);
  padding: 2px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: var(--fw-semibold);
}

.rate { font-weight: var(--fw-bold); font-variant-numeric: tabular-nums; letter-spacing: -0.3px; }
</style>
