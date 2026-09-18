<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getAdminDashboard, type DashboardResp } from '@/api/admin'

const data = ref<DashboardResp | null>(null)
const loading = ref(true)

const SCENARIO_LABEL: Record<string, string> = {
  academic_bachelor: '学术·本科',
  academic_master:   '学术·硕士',
  academic_phd:      '学术·博士',
  job_report:        '职业报告',
  self_media:        '自媒体',
  other:             '其他',
}
const SCENARIO_COLOR: Record<string, string> = {
  academic_bachelor: '#007AFF',
  academic_master:   '#5AC8FA',
  academic_phd:      '#AF52DE',
  job_report:        '#FF9500',
  self_media:        '#FF2D55',
  other:             '#8E8E93',
}

onMounted(async () => {
  try { data.value = await getAdminDashboard() }
  finally { loading.value = false }
})

/** 趋势 SVG 折线：宽度 800、高度 180，输出 detect / newUser / avgAiRate 三条线的 polyline points */
const trendW = 800
const trendH = 180
const trendPad = { l: 40, r: 12, t: 12, b: 24 }
const trendInner = computed(() => ({
  w: trendW - trendPad.l - trendPad.r,
  h: trendH - trendPad.t - trendPad.b,
}))
function buildLine(field: 'detect' | 'newUser' | 'avgAiRate'): string {
  if (!data.value) return ''
  const rows = data.value.trend
  const max = Math.max(1, ...rows.map(r => Number(r[field] || 0)))
  const step = trendInner.value.w / Math.max(1, rows.length - 1)
  return rows.map((r, i) => {
    const x = trendPad.l + i * step
    const y = trendPad.t + trendInner.value.h * (1 - Number(r[field] || 0) / max)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

/** 场景分布 SVG 饼图 */
const pieR = 80
function buildPie() {
  if (!data.value) return [] as Array<{ path: string; color: string; label: string; pct: number }>
  const entries = Object.entries(data.value.scenarioDist)
  const total = entries.reduce((s, [, v]) => s + v, 0)
  if (total === 0) return entries.map(([k]) => ({ path: '', color: SCENARIO_COLOR[k], label: SCENARIO_LABEL[k], pct: 0 }))
  let angle = -Math.PI / 2
  return entries.map(([k, v]) => {
    const pct = v / total
    const sweep = pct * Math.PI * 2
    const x1 = 100 + pieR * Math.cos(angle)
    const y1 = 100 + pieR * Math.sin(angle)
    angle += sweep
    const x2 = 100 + pieR * Math.cos(angle)
    const y2 = 100 + pieR * Math.sin(angle)
    const large = sweep > Math.PI ? 1 : 0
    const path = pct >= 0.999
      ? `M 100 20 A ${pieR} ${pieR} 0 1 1 100 180 A ${pieR} ${pieR} 0 1 1 100 20`
      : `M 100 100 L ${x1.toFixed(1)} ${y1.toFixed(1)} A ${pieR} ${pieR} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} Z`
    return { path, color: SCENARIO_COLOR[k] || '#8E8E93', label: SCENARIO_LABEL[k] || k, pct }
  })
}
const pieSlices = computed(buildPie)
</script>

<template>
  <div v-loading="loading" class="dash-page">
    <!-- KPI 卡 -->
    <div v-if="data" class="kpi-row">
      <el-card class="kpi-card"><div class="kpi-label">今日新增用户</div><div class="kpi-value">{{ data.kpi.todayNewUser }}</div></el-card>
      <el-card class="kpi-card"><div class="kpi-label">今日检测数</div><div class="kpi-value">{{ data.kpi.todayDetect }}</div></el-card>
      <el-card class="kpi-card"><div class="kpi-label">累计用户</div><div class="kpi-value">{{ data.kpi.totalUser }}</div></el-card>
      <el-card class="kpi-card"><div class="kpi-label">累计检测数</div><div class="kpi-value">{{ data.kpi.totalDetect }}</div></el-card>
      <el-card class="kpi-card"><div class="kpi-label">平均 AI 率</div><div class="kpi-value">{{ data.kpi.avgAiRate.toFixed(1) }}%</div></el-card>
    </div>

    <!-- 趋势 + 场景分布 -->
    <div v-if="data" class="mid-row">
      <el-card class="trend-card">
        <template #header>
          <div class="card-title">
            <span>30 天趋势</span>
            <div class="legend">
              <span class="dot" style="background:#007AFF"></span><span>检测量</span>
              <span class="dot" style="background:#34C759"></span><span>新增用户</span>
              <span class="dot" style="background:#FF9500"></span><span>平均 AI 率</span>
            </div>
          </div>
        </template>
        <svg :viewBox="`0 0 ${trendW} ${trendH}`" width="100%" :style="{ height: trendH + 'px' }">
          <line :x1="trendPad.l" :y1="trendPad.t"                       :x2="trendPad.l" :y2="trendH - trendPad.b" stroke="#E5E5EA" />
          <line :x1="trendPad.l" :y1="trendH - trendPad.b" :x2="trendW - trendPad.r" :y2="trendH - trendPad.b" stroke="#E5E5EA" />
          <polyline :points="buildLine('detect')"    fill="none" stroke="#007AFF" stroke-width="2" />
          <polyline :points="buildLine('newUser')"   fill="none" stroke="#34C759" stroke-width="2" />
          <polyline :points="buildLine('avgAiRate')" fill="none" stroke="#FF9500" stroke-width="2" />
        </svg>
      </el-card>

      <el-card class="pie-card">
        <template #header><div class="card-title">场景分布</div></template>
        <div class="pie-wrap">
          <svg viewBox="0 0 200 200" width="200" height="200">
            <path v-for="(s, i) in pieSlices" :key="i" :d="s.path" :fill="s.color" />
          </svg>
          <div class="pie-legend">
            <div v-for="(s, i) in pieSlices" :key="i" class="legend-row">
              <span class="legend-dot" :style="{ background: s.color }"></span>
              <span class="legend-name">{{ s.label }}</span>
              <span class="legend-pct">{{ (s.pct * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- Top 10 -->
    <div v-if="data" class="bot-row">
      <el-card class="bot-card">
        <template #header><div class="card-title">Top 10 高活跃用户（近 7 天）</div></template>
        <el-table :data="data.topUsers" size="small" empty-text="暂无数据">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="userLabel" label="用户标识" />
          <el-table-column prop="detectCount" label="7 天检测数" width="120" align="right" />
        </el-table>
      </el-card>
      <el-card class="bot-card">
        <template #header><div class="card-title">Top 10 待处理反馈</div></template>
        <el-table :data="data.pendingFeedback" size="small" empty-text="暂无待处理">
          <el-table-column prop="category" label="分类" width="90" />
          <el-table-column prop="content" label="内容" show-overflow-tooltip />
          <el-table-column prop="createdAt" label="时间" width="150" />
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.dash-page { display: flex; flex-direction: column; gap: 20px; }
.kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; }
.kpi-card { text-align: center; }
.kpi-label { font-size: 13px; color: rgba(60,60,67,0.60); }
.kpi-value { font-size: 30px; font-weight: 600; letter-spacing: -0.5px; margin-top: 6px; color: #1C1C1E; }

.mid-row { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }
.card-title { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.legend { display: flex; align-items: center; gap: 8px; font-size: 12px; color: rgba(60,60,67,0.72); font-weight: 400; }
.legend .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-left: 12px; }

.pie-wrap { display: flex; align-items: center; gap: 24px; }
.pie-legend { flex: 1; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.legend-row { display: flex; align-items: center; gap: 8px; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
.legend-name { flex: 1; }
.legend-pct { font-variant-numeric: tabular-nums; color: rgba(60,60,67,0.72); }

.bot-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
</style>
