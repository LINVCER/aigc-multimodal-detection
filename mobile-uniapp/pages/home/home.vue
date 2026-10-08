<script setup>
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import { listTasks, getStatistics } from '@/api/detect'
import { SCENARIO_MAP, aiRateColor } from '@/utils/constants'
import AssistantFab from '@/components/AssistantFab.vue'

const tasks = ref([])
const stats = ref(null)     // 后端 /detect/statistics · null 时走本地聚合兜底
const loading = ref(false)

async function load(silent = false) {
  if (!silent) loading.value = true
  // 并发拉 · statistics 拉不到不阻塞主列表；catch 收 request.js 已弹 toast 的错
  const [tasksResp, statsResp] = await Promise.all([
    listTasks().catch(() => null),
    getStatistics().catch(() => null),
  ])
  if (tasksResp) tasks.value = tasksResp
  stats.value = statsResp
  loading.value = false
  uni.stopPullDownRefresh()
}

onShow(load)
onPullDownRefresh(() => load(false))

/* ---------- Wave 3.2 · 微信分享 ---------- */
onShareAppMessage(() => ({
  title: '论文 AIGC 检测 · 一键测你的文档 AI 率',
  path: '/pages/home/home',
  imageUrl: '',   // 可后续换品牌海报
}))
onShareTimeline(() => ({
  title: '论文 AI 率检测 · 段落热力 + 疑似来源分布',
  query: '',
}))

/* ---------- 本周概览 ----------
 * 优先走后端 /detect/statistics：
 *   - 本周检测数 = dailyTrend 最近 7 天 count 求和（准）
 *   - 平均 AI 率 / 达标率 = 后端全局字段（历史累计口径，比"仅本周"样本量大）
 * 后端拉不到（stats == null） → 走本地 tasks 聚合兜底（口径本周准）
 */
const weekStats = computed(() => {
  if (stats.value?.dailyTrend?.length) {
    const last7 = stats.value.dailyTrend.slice(-7)
    const total = last7.reduce((s, r) => s + (r.count || 0), 0)
    return {
      total,
      doneCount: stats.value.done ?? 0,
      avgRate:   stats.value.avgAiRate ?? 0,
      passRate:  Math.round(stats.value.passRate ?? 0),
    }
  }
  // fallback · 本地本周聚合
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

/* ---------- 场景标签（最近检测列表用） ---------- */
const scenarioOf = (k) => SCENARIO_MAP[k] || SCENARIO_MAP.other

/* ---------- 跳转 ----------
 * 主 CTA 与运营轮播跳二级模态选择；助手 / 验真 / 记录直连对应页
 */
function goModalityPicker() { uni.switchTab({ url: '/pages/upload/upload' }) }
function goAssistant() { uni.navigateTo({ url: '/pages/assistant/chat' }) }
function goVerify() { uni.navigateTo({ url: '/pages/verify/verify' }) }

function goRecords() { uni.switchTab({ url: '/pages/index/index' }) }
function goProfile() { uni.switchTab({ url: '/pages/profile/profile' }) }
function goDetail(id) { uni.navigateTo({ url: `/pages/task/detail?id=${id}` }) }

function comingSoon(name) {
  uni.showToast({ title: `${name} 即将上线`, icon: 'none' })
}

/* ---------- 运营轮播 ----------
 * 大图全部由 CSS 渐变 + SVG 线稿绘制，不引入外部图片；
 * 三屏各带一个明确落地动作（target 用字符串，避免函数进 data 被序列化丢弃）
 */
const promoIndex = ref(0)
const PROMOS = [
  { key: 'explain', title: '不只给一个比例', desc: '逐段解释为什么像 AI，定位最可疑的句子', cta: '问小白', target: 'assistant' },
  { key: 'redline', title: '教育部 2026 新规红线', desc: '本科 20% · 硕士 15% · 博士 10%', cta: '立即检测', target: 'upload' },
  { key: 'appeal', title: '原创被误判有路可走', desc: '一键整理申诉材料，不推销「降 AI」', cta: '看申诉指引', target: 'assistant' },
]
function onPromoChange(e) { promoIndex.value = e.detail.current }
function onPromoTap(p) {
  if (p.target === 'assistant') goAssistant()
  else if (p.target === 'upload') goModalityPicker()
}

/* ---------- 语义 ---------- */
const passColor = computed(() =>
  weekStats.value.doneCount === 0 ? '' : (weekStats.value.passRate >= 60 ? 'good' : 'warn')
)
const rateColorOf = (t) => aiRateColor(t.aiRate, t.threshold || 25)
</script>

<template>
  <view class="page">
    <!-- 主 CTA · 品牌渐变卡 · 跳二级模态选择 -->
    <view class="hero-cta" hover-class="hero-cta-hover" @click="goModalityPicker">
      <view class="hero-cta-body">
        <text class="hero-cta-title">立即开始检测</text>
        <text class="hero-cta-desc">上传论文全文，几十秒出 AI 率报告</text>
      </view>
      <text class="hero-cta-arrow">→</text>
    </view>

    <!-- 运营轮播 · 大图自绘（CSS 渐变 + SVG 线稿，不引外部图片） -->
    <view class="promo">
      <swiper
        class="promo-swiper"
        :current="promoIndex"
        circular
        autoplay
        :interval="3000"
        :duration="400"
        @change="onPromoChange"
      >
        <swiper-item v-for="p in PROMOS" :key="p.key">
          <view
            class="promo-slide"
            :class="'ps-' + p.key"
            hover-class="promo-slide-hover"
            @click="onPromoTap(p)"
          >
            <view class="promo-art" :class="'art-' + p.key" />
            <view class="promo-body">
              <text class="promo-title">{{ p.title }}</text>
              <text class="promo-desc">{{ p.desc }}</text>
              <view class="promo-cta">
                <text class="promo-cta-text">{{ p.cta }}</text>
                <text class="promo-cta-arrow">→</text>
              </view>
            </view>
          </view>
        </swiper-item>
      </swiper>
      <view class="promo-dots">
        <view
          v-for="(p, i) in PROMOS" :key="p.key"
          class="promo-dot" :class="{ on: i === promoIndex }"
        />
      </view>
    </view>

    <view class="verify-link" hover-class="verify-link-hover" @click="goVerify"><text class="verify-link-text">收到一份检测报告？输入编号验证真伪</text><text class="verify-link-arrow">›</text></view>

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

    <!-- 论文检测助手入口 -->
    <AssistantFab />
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
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

/* ---------- 运营轮播 · 大图自绘 ---------- */
.promo { margin-top: $sp-4; }
.promo-swiper {
  height: 400rpx;
  border-radius: $radius-hero;
}
.promo-slide {
  position: relative;
  height: 100%;
  padding: $sp-5;
  display: flex; align-items: center;
  border-radius: $radius-hero;
  overflow: hidden;
  box-shadow: $shadow-lift;
  transition: transform $duration-fast $ease-standard;
}
.promo-slide-hover { transform: scale(0.985); }

/* 三屏渐变底 · 各带方向感 */
.ps-explain { background: linear-gradient(135deg, #5E5CE6 0%, #7B7BFF 44%, #64D2FF 100%); }
.ps-redline { background: linear-gradient(135deg, #FF7A00 0%, #FF5B2E 56%, #FF2D55 100%); }
.ps-appeal  { background: linear-gradient(135deg, #12B76A 0%, #00C7BE 58%, #22D3EE 100%); }

/* 右侧大图 · 白色线稿（背景层，不挡点击） */
.promo-art {
  position: absolute;
  top: 0; right: 0;
  width: 360rpx; height: 100%;
  background-repeat: no-repeat;
  background-position: right center;
  background-size: 320rpx 320rpx;
  pointer-events: none;
}
.art-explain {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200' fill='none' stroke='%23FFFFFF' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'><path d='M44 58h84a18 18 0 0 1 18 18v32a18 18 0 0 1-18 18H80l-26 20v-20H44a18 18 0 0 1-18-18V76a18 18 0 0 1 18-18z' opacity='0.55'/><circle cx='68' cy='92' r='5' fill='%23FFFFFF' stroke='none' opacity='0.95'/><circle cx='88' cy='92' r='5' fill='%23FFFFFF' stroke='none' opacity='0.95'/><circle cx='108' cy='92' r='5' fill='%23FFFFFF' stroke='none' opacity='0.95'/><path d='M152 40l6 16 16 6-16 6-6 16-6-16-16-6 16-6z' fill='%23FFFFFF' stroke='none' opacity='0.85'/></svg>");
}
.art-redline {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200' fill='none' stroke='%23FFFFFF' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'><path d='M40 142a62 62 0 0 1 124 0' opacity='0.55'/><path d='M100 142l36-44' stroke-width='5'/><circle cx='100' cy='142' r='8' fill='%23FFFFFF' stroke='none'/><path d='M58 100l9 7M100 80v11M142 100l-9 7' opacity='0.75'/><path d='M154 40l30 52h-60z' fill='%23FFFFFF' stroke='none' opacity='0.92'/><path d='M154 56v16M154 82h.1' stroke='%23FF5B2E' stroke-width='5'/></svg>");
}
.art-appeal {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 200' fill='none' stroke='%23FFFFFF' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'><path d='M60 34h56l26 26v100a10 10 0 0 1-10 10H60a10 10 0 0 1-10-10V44a10 10 0 0 1 10-10z' opacity='0.5'/><path d='M116 34v26h26' opacity='0.5'/><path d='M78 104l14 14 30-30' stroke-width='6' opacity='0.95'/><path d='M78 138h44' opacity='0.45'/></svg>");
}

.promo-body { position: relative; z-index: 2; flex: 1; display: flex; flex-direction: column; }
.promo-title {
  display: block;
  font-size: $fs-title-3;
  font-weight: $fw-bold;
  color: #FFFFFF;
  letter-spacing: $tracking-snug;
}
.promo-desc {
  display: block;
  margin-top: $sp-1;
  max-width: 360rpx;
  font-size: $fs-subhead;
  color: rgba(255, 255, 255, 0.88);
  line-height: $lh-normal;
}
.promo-cta {
  align-self: flex-start;
  margin-top: $sp-3;
  display: inline-flex; align-items: center;
  height: 56rpx;
  padding: 0 $sp-3;
  border-radius: $radius-pill;
  background: rgba(255, 255, 255, 0.94);
}
.promo-cta-text { font-size: $fs-subhead; font-weight: $fw-semibold; color: $label-primary; }
.promo-cta-arrow { font-size: $fs-subhead; color: $label-primary; margin-left: 6rpx; }

/* 指示点 · 当前项拉长 */
.promo-dots {
  margin-top: $sp-3;
  display: flex; justify-content: center; align-items: center;
  gap: 10rpx;
}
.promo-dot {
  width: 12rpx; height: 12rpx;
  border-radius: $radius-pill;
  background: rgba(60, 60, 67, 0.22);
  transition: width $duration-fast $ease-standard, background $duration-fast;
}
.promo-dot.on { width: 32rpx; background: $brand-primary; }

/* ---------- 报告验真入口 ---------- */
.verify-link { margin-top: $sp-3; padding: $sp-2 $sp-3; display: flex; justify-content: space-between; align-items: center; border-radius: $radius-md; background: $brand-primary-wash; }
.verify-link-hover { opacity: 0.7; }
.verify-link-text { font-size: $fs-footnote; color: $brand-primary; }
.verify-link-arrow { font-size: $fs-headline; color: $brand-primary; }

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
