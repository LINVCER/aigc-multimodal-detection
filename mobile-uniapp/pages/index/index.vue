<script setup>
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { listTasks } from '@/api/detect'
import { SCENARIO_MAP, aiRateColor } from '@/utils/constants'
import StatusChip from '@/components/StatusChip.vue'
import EmptyState from '@/components/EmptyState.vue'
import Skeleton from '@/components/Skeleton.vue'

const tasks = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const statusFilter = ref('ALL')
let pollTimer = null

const STATUS_TABS = [
  { key: 'ALL',     text: '全部' },
  { key: 'RUNNING', text: '进行中' },
  { key: 'DONE',    text: '已完成' },
  { key: 'FAILED',  text: '失败' },
]

const statusCount = computed(() => {
  const c = { ALL: tasks.value.length, RUNNING: 0, DONE: 0, FAILED: 0, PENDING: 0 }
  tasks.value.forEach(t => { c[t.status] = (c[t.status] || 0) + 1 })
  // PENDING 归入 RUNNING（用户视角都是"进行中"）
  c.RUNNING += c.PENDING
  return c
})

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return tasks.value.filter((t) => {
    const kwHit = !kw || (t.paperTitle || '').toLowerCase().includes(kw)
    let stHit
    if (statusFilter.value === 'ALL') stHit = true
    else if (statusFilter.value === 'RUNNING') stHit = t.status === 'RUNNING' || t.status === 'PENDING'
    else stHit = t.status === statusFilter.value
    return kwHit && stHit
  })
})

const runningCount = computed(() => statusCount.value.RUNNING || 0)

const weekStats = computed(() => {
  const weekAgo = Date.now() - 7 * 24 * 3600 * 1000
  const inWeek = tasks.value.filter(t => {
    if (!t.createdAt) return false
    const ts = Date.parse(String(t.createdAt).replace(' ', 'T'))
    return !Number.isNaN(ts) && ts >= weekAgo
  })
  const done = inWeek.filter(t => t.status === 'DONE' && typeof t.aiRate === 'number')
  const avgRate = done.length ? done.reduce((s, t) => s + t.aiRate, 0) / done.length : 0
  const passed = done.filter(t => t.aiRate <= (t.threshold || 25)).length
  const passRate = done.length ? Math.round(passed / done.length * 100) : 0
  return { total: inWeek.length, doneCount: done.length, avgRate, passRate }
})

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try { tasks.value = await listTasks() }
  catch (e) { error.value = e?.message || '加载失败' }
  finally { loading.value = false; uni.stopPullDownRefresh() }
}

function ensurePolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (runningCount.value > 0) load(true)
    else stopPolling()
  }, 4000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

onShow(async () => {
  await load()
  if (runningCount.value > 0) ensurePolling()
  else stopPolling()
})
onPullDownRefresh(load)

function goDetail(id) { uni.navigateTo({ url: `/pages/task/detail?id=${id}` }) }
function goUpload() { uni.switchTab({ url: '/pages/upload/upload' }) }

const scenarioOf = (t) => SCENARIO_MAP[t?.scenario] || SCENARIO_MAP.other
const isPass     = (t) => typeof t.aiRate === 'number' && t.aiRate <= (t.threshold || 25)
const rateColorOf = (t) => aiRateColor(t.aiRate, t.threshold || 25)
</script>

<template>
  <view class="page">
    <!-- 1. Large Title Hero -->
    <view class="hero-header">
      <text class="large-title">检测记录</text>
      <text class="hero-sub">AI 率保持在场景红线以内即为达标</text>
    </view>

    <!-- 2. 本周概览 KPI 卡（DONE 前显示 dash 占位）-->
    <view class="stats-card">
      <view class="stat">
        <text class="stat-value">{{ weekStats.total }}</text>
        <text class="stat-label">本周检测</text>
      </view>
      <view class="stat-divider" />
      <view class="stat">
        <text class="stat-value" :class="{ muted: weekStats.doneCount === 0 }">
          {{ weekStats.doneCount ? weekStats.avgRate.toFixed(1) + '%' : '—' }}
        </text>
        <text class="stat-label">平均 AI 率</text>
      </view>
      <view class="stat-divider" />
      <view class="stat">
        <text class="stat-value" :class="{ green: weekStats.doneCount > 0, muted: weekStats.doneCount === 0 }">
          {{ weekStats.doneCount ? weekStats.passRate + '%' : '—' }}
        </text>
        <text class="stat-label">达标率</text>
      </view>
    </view>

    <!-- 3. 检测中提示条 -->
    <view v-if="runningCount > 0" class="running-banner">
      <view class="pulse-dot" />
      <text class="banner-text">{{ runningCount }} 项检测中，稍候自动刷新</text>
    </view>

    <!-- 4. 搜索栏 + Segmented 状态筛选 -->
    <view class="search-wrap">
      <view class="search">
        <view class="search-icon" />
        <input
          class="search-input"
          v-model="keyword"
          placeholder="搜索论文标题"
          placeholder-style="color: rgba(60,60,67,0.30)"
          confirm-type="search"
        />
        <text v-if="keyword" class="search-clear" @click="keyword = ''">×</text>
      </view>

      <view class="segmented">
        <view
          v-for="opt in STATUS_TABS" :key="opt.key"
          class="seg" :class="{ active: statusFilter === opt.key }"
          @click="statusFilter = opt.key"
        >
          <text class="seg-text">{{ opt.text }}</text>
          <text v-if="statusCount[opt.key]" class="seg-count">{{ statusCount[opt.key] }}</text>
        </view>
      </view>
    </view>

    <!-- 5. 内容态 -->
    <view v-if="loading && tasks.length === 0" class="skeleton-wrap">
      <view v-for="i in 3" :key="i" class="task-card skeleton-card">
        <view class="sk sk-chip" />
        <view class="sk sk-title" />
        <view class="sk sk-meta" />
        <view class="sk sk-rate" />
      </view>
    </view>

    <EmptyState
      v-else-if="error && tasks.length === 0"
      icon="!" :title="error" desc="下拉可重试，或检查网络后重新进入"
      actionText="重新加载" @action="load()"
    />
    <EmptyState
      v-else-if="filtered.length === 0 && !keyword && statusFilter === 'ALL'"
      icon="✎" title="还没有检测记录"
      desc="上传第一份论文，几十秒内拿到 AI 率报告"
      actionText="去上传" @action="goUpload"
    />
    <EmptyState
      v-else-if="filtered.length === 0"
      icon="?" title="没有匹配的记录"
      desc="试试其它关键词或筛选条件"
    />

    <view v-else class="task-list">
      <view
        v-for="t in filtered" :key="t.id"
        class="task-card" hover-class="task-card-hover"
        @click="goDetail(t.id)"
      >
        <view class="task-head">
          <view
            class="scenario-chip"
            :style="{ background: scenarioOf(t).wash, color: scenarioOf(t).tint }"
          >{{ scenarioOf(t).label }}</view>
          <StatusChip :status="t.status" />
        </view>

        <text class="task-title">{{ t.paperTitle }}</text>

        <view class="task-meta">
          <text class="meta-time">{{ t.createdAt }}</text>
          <text class="meta-sep">·</text>
          <text class="meta-thr">红线 ≤ {{ t.threshold }}%</text>
        </view>

        <view class="task-footer">
          <view v-if="t.status === 'DONE' && t.aiRate != null" class="rate-block">
            <text class="rate-value" :style="{ color: rateColorOf(t) }">{{ t.aiRate.toFixed(1) }}</text>
            <text class="rate-unit" :style="{ color: rateColorOf(t) }">%</text>
            <view class="pass-badge" :class="isPass(t) ? 'pass-ok' : 'pass-fail'">
              {{ isPass(t) ? '达标' : '超红线' }}
            </view>
          </view>
          <view v-else-if="t.status === 'RUNNING' || t.status === 'PENDING'" class="status-inline running">
            <view class="pulse-dot small" />
            <text>正在检测</text>
          </view>
          <text v-else-if="t.status === 'FAILED'" class="status-inline failed">检测失败，点击查看</text>
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding-bottom: $sp-8;
  background: $bg-grouped-primary;
}

/* ---------- 1. Hero Header ---------- */
.hero-header {
  padding: $sp-6 $sp-5 $sp-3;
}
.large-title {
  display: block;
  font-size: $fs-large-title;
  font-weight: $fw-bold;
  line-height: $lh-tight;
  letter-spacing: $tracking-tight;
  color: $label-primary;
}
.hero-sub {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-top: $sp-1;
}

/* ---------- 2. 本周概览 KPI 卡 ---------- */
.stats-card {
  margin: 0 $sp-4;
  padding: $sp-5 $sp-3;
  background: $bg-primary;
  border-radius: $radius-card;
  box-shadow: $shadow-card;
  display: flex;
  align-items: stretch;
}
.stat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: $sp-1;
}
.stat-value {
  font-size: $fs-title-2;
  font-weight: $fw-bold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
  font-variant-numeric: tabular-nums;
  &.muted { color: $label-tertiary; font-weight: $fw-medium; }
  &.green { color: $success-solid; }
}
.stat-label {
  font-size: $fs-caption-1;
  color: $label-secondary;
}
.stat-divider {
  width: $stroke-hairline;
  background: $separator;
  margin: $sp-1 0;
}

/* ---------- 3. 检测中提示条 ---------- */
.running-banner {
  margin: $sp-3 $sp-4 0;
  padding: $sp-2 $sp-3;
  background: $info-bg;
  border-radius: $radius-md;
  display: flex;
  align-items: center;
  gap: $sp-2;
}
.banner-text {
  font-size: $fs-footnote;
  color: $info-fg;
  font-weight: $fw-medium;
}
.pulse-dot {
  width: 16rpx;
  height: 16rpx;
  border-radius: 50%;
  background: $info-solid;
  animation: pulse-dot 1.4s ease-in-out infinite;
  &.small { width: 12rpx; height: 12rpx; background: $warning-solid; }
}
@keyframes pulse-dot {
  0%, 100% { opacity: 0.35; transform: scale(0.9); }
  50%      { opacity: 1;    transform: scale(1.1); }
}

/* ---------- 4. 搜索 + Segmented ---------- */
.search-wrap {
  padding: $sp-3 $sp-4 $sp-2;
}
.search {
  display: flex;
  align-items: center;
  height: 72rpx;
  padding: 0 $sp-3;
  background: $fill-tertiary;
  border-radius: $radius-btn;
}
.search-icon {
  width: 32rpx;
  height: 32rpx;
  margin-right: $sp-2;
  /* SVG 放大镜 · rgba stroke（image 不继承 CSS color） */
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='rgba(60,60,67,0.6)' stroke-width='2.4' stroke-linecap='round'><circle cx='11' cy='11' r='7'/><line x1='21' y1='21' x2='16.65' y2='16.65'/></svg>") no-repeat center / contain;
}
.search-input {
  flex: 1;
  height: 100%;
  font-size: $fs-callout;
  color: $label-primary;
}
.search-clear {
  color: $label-secondary;
  font-size: $fs-body;
  padding: 0 $sp-2;
  line-height: 1;
}

.segmented {
  display: flex;
  margin-top: $sp-3;
  padding: 6rpx;
  background: $fill-tertiary;
  border-radius: $radius-btn;
}
.seg {
  flex: 1;
  height: 60rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6rpx;
  border-radius: 14rpx;
  transition: all $duration-fast $ease-standard;
  &.active {
    background: $bg-primary;
    box-shadow: 0 3rpx 8rpx rgba(0, 0, 0, 0.05);
  }
}
.seg-text {
  font-size: $fs-subhead;
  color: $label-primary;
  font-weight: $fw-medium;
  .seg.active & { font-weight: $fw-semibold; }
}
.seg-count {
  font-size: $fs-caption-2;
  font-weight: $fw-semibold;
  color: $label-secondary;
  min-width: 28rpx;
  padding: 0 8rpx;
  height: 28rpx;
  line-height: 28rpx;
  border-radius: $radius-pill;
  background: $fill-secondary;
  text-align: center;
  .seg.active & { background: $brand-primary; color: #FFFFFF; }
}

/* ---------- 5. 骨架屏 ---------- */
.skeleton-wrap { padding: $sp-3 $sp-4 0; display: flex; flex-direction: column; gap: $sp-3; }
.skeleton-card { padding: $sp-4; }
.sk { border-radius: $radius-sm; @include skeleton-shimmer; }
.sk-chip  { width: 140rpx; height: 36rpx; }
.sk-title { width: 80%; height: 40rpx; margin-top: $sp-3; }
.sk-meta  { width: 55%; height: 28rpx; margin-top: $sp-2; }
.sk-rate  { width: 40%; height: 60rpx; margin-top: $sp-3; }

/* ---------- 6. 任务卡列表 ---------- */
.task-list {
  padding: $sp-3 $sp-4 0;
  display: flex;
  flex-direction: column;
  gap: $sp-3;
}
.task-card {
  padding: $sp-4;
  background: $bg-primary;
  border-radius: $radius-card;
  box-shadow: $shadow-card;
  transition: transform $duration-fast $ease-standard, background $duration-fast;
}
.task-card-hover {
  background: rgba(60, 60, 67, 0.04);
  transform: scale(0.99);
}
.task-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: $sp-2;
}
.scenario-chip {
  display: inline-flex;
  align-items: center;
  height: 40rpx;
  padding: 0 $sp-2;
  border-radius: $radius-pill;
  font-size: $fs-caption-1;
  font-weight: $fw-semibold;
  letter-spacing: 0.5rpx;
}
.task-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin-top: $sp-3;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  line-height: $lh-snug;
  color: $label-primary;
  letter-spacing: $tracking-snug;
}
.task-meta {
  margin-top: $sp-2;
  display: flex;
  align-items: center;
  font-size: $fs-caption-1;
  color: $label-secondary;
}
.meta-sep { margin: 0 $sp-2; opacity: 0.5; }

.task-footer {
  margin-top: $sp-4;
  padding-top: $sp-3;
  border-top: $stroke-hairline solid $separator;
  min-height: 56rpx;
  display: flex;
  align-items: center;
}
.rate-block {
  display: flex;
  align-items: baseline;
  gap: $sp-1;
  flex: 1;
}
.rate-value {
  font-size: 60rpx;
  font-weight: $fw-bold;
  line-height: 1;
  letter-spacing: $tracking-tight;
  font-variant-numeric: tabular-nums;
}
.rate-unit {
  font-size: $fs-callout;
  font-weight: $fw-semibold;
}
.pass-badge {
  margin-left: auto;
  height: 40rpx;
  padding: 0 $sp-2;
  border-radius: $radius-pill;
  font-size: $fs-caption-1;
  font-weight: $fw-semibold;
  line-height: 40rpx;
  &.pass-ok   { background: $success-bg; color: $success-fg; }
  &.pass-fail { background: $danger-bg;  color: $danger-fg;  }
}

.status-inline {
  display: flex;
  align-items: center;
  gap: $sp-2;
  font-size: $fs-subhead;
  font-weight: $fw-medium;
  &.running { color: $warning-fg; }
  &.failed  { color: $danger-fg; }
}
</style>
