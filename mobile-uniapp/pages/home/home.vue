<script setup>
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { listTasks } from '@/api/detect'
import { SCENARIO_MAP, aiRateColor } from '@/utils/constants'
import { useAuth } from '@/store/auth'

const auth = useAuth()

const tasks = ref([])
const loading = ref(false)

async function load(silent = false) {
  if (!silent) loading.value = true
  try { tasks.value = await listTasks() }
  catch (e) { /* mock 模式下不报 */ }
  finally { loading.value = false; uni.stopPullDownRefresh() }
}

onShow(load)
onPullDownRefresh(() => load(false))

/* ---------- 本周概览 ---------- */
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

/* ---------- 最近 3 条 ---------- */
const recent = computed(() => tasks.value.slice(0, 3))

/* ---------- 场景快选 ---------- */
const SCENARIOS = [
  'academic_bachelor', 'academic_master', 'academic_phd',
  'job_report', 'self_media', 'other',
]
const scenarioOf = (k) => SCENARIO_MAP[k] || SCENARIO_MAP.other

/* ---------- 跳转 ----------
 * A 方案：主 CTA 跳二级模态选择；quick-tile 直连三级（跳过二级）
 * 场景 chip 跳论文三级 + 预选场景（switchTab 不能传参走 storage 兜底）
 */
function goModalityPicker() { uni.switchTab({ url: '/pages/upload/upload' }) }

function goText(scenarioKey, mode) {
  if (scenarioKey) uni.setStorageSync('pending_scenario', scenarioKey)
  if (mode) uni.setStorageSync('pending_upload_mode', mode)
  uni.navigateTo({ url: '/pages/upload/text' })
}
function goAudio() { uni.navigateTo({ url: '/pages/upload/audio' }) }

function goRecords() { uni.switchTab({ url: '/pages/index/index' }) }
function goProfile() { uni.switchTab({ url: '/pages/profile/profile' }) }
function goDetail(id) { uni.navigateTo({ url: `/pages/task/detail?id=${id}` }) }

function comingSoon(name) {
  uni.showToast({ title: `${name} 即将上线`, icon: 'none' })
}

/* ---------- 语义 ---------- */
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6)  return '夜深了'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})
const passColor = computed(() =>
  weekStats.value.doneCount === 0 ? '' : (weekStats.value.passRate >= 60 ? 'good' : 'warn')
)
const rateColorOf = (t) => aiRateColor(t.aiRate, t.threshold || 25)
</script>

<template>
  <view class="page">
    <!-- Hero 头部 -->
    <view class="hero-header">
      <text class="greeting">{{ greeting }}{{ auth.username ? '，' + auth.username : '' }}</text>
      <text class="large-title">开始一次检测</text>
      <text class="hero-sub">AI 率 · 段落热力 · 疑似来源分布</text>
    </view>

    <!-- 主 CTA · 品牌渐变卡 · 跳二级模态选择 -->
    <view class="hero-cta" hover-class="hero-cta-hover" @click="goModalityPicker">
      <view class="hero-cta-body">
        <text class="hero-cta-title">立即开始检测</text>
        <text class="hero-cta-desc">选择内容类型：论文 / 音频 / 图像</text>
      </view>
      <text class="hero-cta-arrow">→</text>
    </view>

    <!-- 快捷入口 2×2 · 直连三级页 -->
    <view class="quick-grid">
      <view class="quick-tile" hover-class="quick-tile-hover" @click="goText()">
        <view class="quick-icon quick-icon-file" />
        <text class="quick-label">论文文件</text>
        <text class="quick-desc">PDF / DOC</text>
      </view>
      <view class="quick-tile" hover-class="quick-tile-hover" @click="goText(null, 'paste')">
        <view class="quick-icon quick-icon-paste" />
        <text class="quick-label">粘贴文本</text>
        <text class="quick-desc">即时打分</text>
      </view>
      <view class="quick-tile" hover-class="quick-tile-hover" @click="goAudio">
        <view class="quick-icon quick-icon-audio" />
        <text class="quick-label">音频检测</text>
        <text class="quick-desc">MP3 / WAV</text>
      </view>
      <view class="quick-tile" hover-class="quick-tile-hover" @click="goRecords">
        <view class="quick-icon quick-icon-history" />
        <text class="quick-label">检测记录</text>
        <text class="quick-desc">{{ tasks.length ? tasks.length + ' 份' : '暂无' }}</text>
      </view>
    </view>

    <!-- 本周概览 -->
    <text class="section-label">本周概览</text>
    <view class="stats-card">
      <view class="stat">
        <text class="stat-value">{{ weekStats.total }}</text>
        <text class="stat-label">检测次数</text>
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
        <text class="stat-value" :class="passColor || 'muted'">
          {{ weekStats.doneCount ? weekStats.passRate + '%' : '—' }}
        </text>
        <text class="stat-label">达标率</text>
      </view>
    </view>

    <!-- 场景快选 -->
    <text class="section-label">按场景检测</text>
    <scroll-view scroll-x class="scenario-scroll" show-scrollbar="false">
      <view class="scenario-strip">
        <view
          v-for="k in SCENARIOS" :key="k"
          class="scenario-chip"
          :style="{ background: scenarioOf(k).wash, color: scenarioOf(k).tint }"
          hover-class="scenario-chip-hover"
          @click="goText(k)"
        >
          <text class="scenario-label">{{ scenarioOf(k).label }}</text>
          <text class="scenario-th">≤ {{ scenarioOf(k).threshold }}%</text>
        </view>
      </view>
    </scroll-view>

    <!-- 最近检测 -->
    <view class="section-label-line">
      <text class="section-label no-pad">最近检测</text>
      <text v-if="tasks.length" class="more-link" @click="goRecords">全部 ›</text>
    </view>

    <view v-if="!loading && recent.length === 0" class="recent-empty">
      <text class="recent-empty-text">还没有检测记录，点击上方开始第一次</text>
    </view>

    <view v-else class="recent-list">
      <view
        v-for="t in recent" :key="t.id"
        class="recent-card" hover-class="recent-card-hover"
        @click="goDetail(t.id)"
      >
        <view class="recent-head">
          <view
            class="recent-chip"
            :style="{ background: scenarioOf(t.scenario).wash, color: scenarioOf(t.scenario).tint }"
          >{{ scenarioOf(t.scenario).label }}</view>
          <text v-if="t.status === 'DONE' && t.aiRate != null" class="recent-rate" :style="{ color: rateColorOf(t) }">
            {{ t.aiRate.toFixed(1) }}%
          </text>
          <text v-else-if="t.status === 'RUNNING' || t.status === 'PENDING'" class="recent-status warn">检测中</text>
          <text v-else-if="t.status === 'FAILED'" class="recent-status fail">失败</text>
        </view>
        <text class="recent-title">{{ t.paperTitle }}</text>
        <text class="recent-time">{{ t.createdAt }}</text>
      </view>
    </view>

    <text class="privacy">
      论文原文加密存储，30 天后自动删除；报告保留 3 年
    </text>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

/* ---------- Hero ---------- */
.hero-header { padding: $sp-3 $sp-1 $sp-4; }
.greeting {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-bottom: $sp-1;
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

/* ---------- 主 CTA · 品牌渐变卡 ---------- */
.hero-cta {
  margin-top: $sp-2;
  padding: $sp-5 $sp-4;
  border-radius: $radius-card;
  background: $brand-gradient-vivid;
  display: flex; align-items: center; justify-content: space-between;
  box-shadow: $shadow-lift;
  transition: transform $duration-fast $ease-standard;
}
.hero-cta-hover { transform: scale(0.98); }
.hero-cta-body { flex: 1; }
.hero-cta-title {
  display: block;
  font-size: $fs-title-3;
  font-weight: $fw-semibold;
  color: #FFFFFF;
  letter-spacing: $tracking-snug;
}
.hero-cta-desc {
  display: block;
  font-size: $fs-subhead;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 6rpx;
}
.hero-cta-arrow {
  color: #FFFFFF;
  font-size: 44rpx;
  margin-left: $sp-3;
}

/* ---------- 快捷入口 2×2 ---------- */
.quick-grid {
  margin-top: $sp-4;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $sp-2;
}
.quick-tile {
  @include card;
  padding: $sp-4;
  transition: transform $duration-fast $ease-standard;
}
.quick-tile-hover { transform: scale(0.97); background: rgba(60, 60, 67, 0.03); }
.quick-icon {
  width: 72rpx; height: 72rpx;
  border-radius: $radius-md;
  margin-bottom: $sp-2;
}
.quick-icon-file {
  background: $brand-primary-wash url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23007AFF' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><polyline points='14 3 14 8 19 8'/><line x1='8' y1='13' x2='16' y2='13'/><line x1='8' y1='17' x2='13' y2='17'/></svg>") no-repeat center / 44rpx 44rpx;
}
.quick-icon-paste {
  background: rgba(88, 86, 214, 0.10) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%235856D6' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='8' y='2' width='8' height='4' rx='1'/><path d='M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'/><line x1='9' y1='12' x2='15' y2='12'/><line x1='9' y1='16' x2='13' y2='16'/></svg>") no-repeat center / 44rpx 44rpx;
}
.quick-icon-history {
  background: rgba(0, 199, 190, 0.10) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2300C7BE' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M3 12a9 9 0 1 0 3-6.7'/><path d='M3 4v5h5'/><path d='M12 7v5l4 2'/></svg>") no-repeat center / 44rpx 44rpx;
}
.quick-icon-audio {
  background: rgba(255, 45, 85, 0.10) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FF2D55' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M9 18V5l12-2v13'/><circle cx='6' cy='18' r='3'/><circle cx='18' cy='16' r='3'/></svg>") no-repeat center / 44rpx 44rpx;
}
.quick-label {
  display: block;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
}
.quick-desc {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  margin-top: 4rpx;
}

/* ---------- Section Label ---------- */
.section-label {
  display: block;
  padding: $sp-5 $sp-3 $sp-2;
  font-size: $fs-footnote;
  font-weight: $fw-medium;
  color: $label-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wide;
  &.no-pad { padding: 0; }
}
.section-label-line {
  padding: $sp-5 $sp-3 $sp-2;
  display: flex; justify-content: space-between; align-items: center;
}
.more-link {
  font-size: $fs-subhead;
  color: $brand-primary;
  font-weight: $fw-medium;
}

/* ---------- 本周概览 ---------- */
.stats-card {
  @include card;
  padding: $sp-4 $sp-2;
  display: flex; align-items: stretch;
}
.stat {
  flex: 1;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: $sp-1;
}
.stat-value {
  font-size: $fs-title-2;
  font-weight: $fw-bold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
  font-variant-numeric: tabular-nums;
  &.muted { color: $label-tertiary; font-weight: $fw-medium; }
  &.good  { color: $success-solid; }
  &.warn  { color: $warning-solid; }
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

/* ---------- 场景快选 ---------- */
.scenario-scroll { white-space: nowrap; }
.scenario-strip {
  display: inline-flex; gap: $sp-2;
  padding: $sp-1 $sp-1;
}
.scenario-chip {
  display: inline-flex; flex-direction: column;
  padding: $sp-2 $sp-3;
  border-radius: $radius-lg;
  min-width: 180rpx;
  transition: transform $duration-fast $ease-standard;
}
.scenario-chip-hover { transform: scale(0.96); }
.scenario-label {
  font-size: $fs-subhead;
  font-weight: $fw-semibold;
  letter-spacing: $tracking-snug;
}
.scenario-th {
  font-size: $fs-caption-2;
  opacity: 0.75;
  font-weight: $fw-medium;
  margin-top: 4rpx;
  font-variant-numeric: tabular-nums;
}

/* ---------- 最近检测 ---------- */
.recent-empty {
  @include card;
  padding: $sp-6 $sp-4;
  text-align: center;
}
.recent-empty-text {
  font-size: $fs-subhead;
  color: $label-secondary;
}
.recent-list {
  display: flex; flex-direction: column; gap: $sp-2;
}
.recent-card {
  @include card;
  padding: $sp-3 $sp-4;
  transition: background $duration-fast, transform $duration-fast $ease-standard;
}
.recent-card-hover {
  background: rgba(60, 60, 67, 0.04);
  transform: scale(0.99);
}
.recent-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: $sp-2;
}
.recent-chip {
  display: inline-flex; align-items: center;
  height: 36rpx;
  padding: 0 $sp-2;
  border-radius: $radius-pill;
  font-size: $fs-caption-1;
  font-weight: $fw-semibold;
}
.recent-rate {
  font-size: $fs-headline;
  font-weight: $fw-bold;
  letter-spacing: $tracking-snug;
  font-variant-numeric: tabular-nums;
}
.recent-status {
  font-size: $fs-subhead;
  font-weight: $fw-medium;
  &.warn { color: $warning-fg; }
  &.fail { color: $danger-fg; }
}
.recent-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  overflow: hidden;
  font-size: $fs-callout;
  font-weight: $fw-medium;
  color: $label-primary;
}
.recent-time {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  margin-top: 4rpx;
}

/* ---------- 隐私提示 ---------- */
.privacy {
  display: block;
  margin-top: $sp-6;
  font-size: $fs-caption-1;
  color: $label-secondary;
  text-align: center;
  line-height: $lh-normal;
  padding: 0 $sp-5;
}
</style>
