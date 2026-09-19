<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad, onShareAppMessage } from '@dcloudio/uni-app'
import { getTaskDetail, requestHumanize, retryTask, cancelTask } from '@/api/detect'
import { downloadReportPdf } from '@/api/report'
import { SOURCE_MAP, COLOR, paragraphRisk, aiRateColor } from '@/utils/constants'
import { diffChars } from '@/utils/diff'
import Skeleton from '@/components/Skeleton.vue'
import FeedbackSheet from '@/components/FeedbackSheet.vue'

const feedbackOpen = ref(false)

const detail = ref(null)
const loading = ref(true)
const loadError = ref('')
const retrying = ref(false)
const rewrittenMap = ref({})
const humanizingMap = ref({})
const diffOpenMap = ref({})
const expandedMap = ref({})
const scrollIntoId = ref('')
let pollTimer = null
let taskId = null

async function load() {
  loadError.value = ''
  try { detail.value = await getTaskDetail(taskId) }
  catch (e) { loadError.value = e?.message || '加载失败' }
  finally { loading.value = false }
}
function ensurePolling() {
  if (pollTimer) return
  const s = detail.value?.status
  if (s !== 'PENDING' && s !== 'RUNNING') return
  pollTimer = setInterval(async () => {
    await load()
    const st = detail.value?.status
    if (st === 'DONE' || st === 'FAILED') stopPoll()
  }, 3000)
}
function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
onUnmounted(stopPoll)

/* Wave 3.2 · 微信分享 · 报告脱敏：只带 taskId 让接收方登录后可见完整详情 */
onShareAppMessage(() => {
  const d = detail.value
  const rate = (d?.status === 'DONE' && d?.aiRate != null) ? ` · AI 率 ${d.aiRate.toFixed(1)}%` : ''
  return {
    title: `AIGC 检测报告${rate}`,
    path: d?.id ? `/pages/task/detail?id=${d.id}` : '/pages/home/home',
  }
})

async function onRetry() {
  retrying.value = true
  try {
    await retryTask(taskId)
    uni.showToast({ title: '已重新提交', icon: 'success' })
    await load()
    ensurePolling()
  } catch (e) {
    uni.showToast({ title: e?.message || '重试失败', icon: 'none' })
  } finally { retrying.value = false }
}

const cancelling = ref(false)
async function onCancel() {
  const ok = await new Promise((resolve) => {
    uni.showModal({
      title: '取消检测',
      content: '确定取消本次检测？取消后可在列表长按重新提交。',
      confirmColor: '#FF3B30', cancelColor: '#007AFF',
      success: (r) => resolve(r.confirm),
      fail: () => resolve(false),
    })
  })
  if (!ok) return
  cancelling.value = true
  try {
    await cancelTask(taskId)
    uni.showToast({ title: '已取消', icon: 'success' })
    stopPoll()
    await load()
  } finally { cancelling.value = false }
}

const downloading = ref(false)
async function onDownload() {
  if (downloading.value) return
  downloading.value = true
  try { await downloadReportPdf(taskId, detail.value?.paperTitle) }
  finally { downloading.value = false }
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/index/index' })
}

onLoad(async (query) => {
  taskId = Number(query.id)
  if (!taskId || Number.isNaN(taskId)) {
    loadError.value = '无效的任务号'
    loading.value = false
    return
  }
  await load()
  ensurePolling()
})

const pass = computed(() => {
  const d = detail.value
  return d && d.aiRate != null && d.aiRate <= d.threshold
})
const summaryColor = computed(() => aiRateColor(detail.value?.aiRate, detail.value?.threshold))

// 环形进度 (SVG r=86 → 周长 ≈ 540.354)
const ringCircumference = 2 * Math.PI * 86
const ringOffset = computed(() => {
  const d = detail.value
  if (!d || d.aiRate == null) return ringCircumference
  const pct = Math.min(100, Math.max(0, d.aiRate)) / 100
  return ringCircumference * (1 - pct)
})
const ringThresholdOffset = computed(() => {
  const d = detail.value
  if (!d || d.threshold == null) return ringCircumference
  const pct = Math.min(100, Math.max(0, d.threshold)) / 100
  return ringCircumference * (1 - pct)
})

const sortedSources = computed(() => {
  if (!detail.value?.sourceLabels) return []
  return Object.entries(detail.value.sourceLabels)
    .sort((a, b) => b[1] - a[1])
    .map(([label, ratio]) => ({ label, ratio }))
})

const bodyStats = computed(() => {
  if (!detail.value?.paragraphs) return null
  const body = detail.value.paragraphs.filter(p => !p.excluded).length
  const excluded = detail.value.paragraphs.length - body
  return { body, excluded }
})

const EXCLUDE_REASON_LABEL = {
  reference: '参考文献',
  acknowledgement: '致谢',
  appendix: '附录',
  sectionTitle: '章节标题',
  caption: '图表标题',
}

/**
 * 改进建议：改用 severity dot + 语义色，去掉 emoji
 * severity: 'danger' | 'warn' | 'info' | 'success'
 */
const suggestions = computed(() => {
  const d = detail.value
  if (!d || d.status !== 'DONE' || d.aiRate == null) return []
  const out = []

  if (d.aiRate > d.threshold) {
    const gap = (d.aiRate - d.threshold).toFixed(1)
    out.push({
      title: `AI 率超线 ${gap} 个百分点`,
      body: `你的 AI 率 ${d.aiRate.toFixed(1)}% 超过 ${d.threshold}% 红线。建议重点修改标红段落，用自己的话重写核心观点。`,
      severity: 'danger',
    })
  } else if (d.aiRate > d.threshold * 0.7) {
    out.push({
      title: '接近红线，仍有修改空间',
      body: `AI 率 ${d.aiRate.toFixed(1)}%，距 ${d.threshold}% 红线不足 ${(d.threshold - d.aiRate).toFixed(1)} 个百分点。建议对标黄段落小幅改写。`,
      severity: 'warn',
    })
  } else {
    out.push({
      title: '整体达标',
      body: `AI 率 ${d.aiRate.toFixed(1)}%，明显低于 ${d.threshold}% 红线。继续保持原创性写作。`,
      severity: 'success',
    })
  }

  const highRisk = (d.paragraphs || []).filter(p => !p.excluded && (p.calibratedProb || 0) >= 0.7)
  if (highRisk.length > 0) {
    const idxList = highRisk.slice(0, 5).map(p => '段' + (p.paragraphIdx + 1)).join('、')
    out.push({
      title: `${highRisk.length} 段高疑似 AI，优先处理`,
      body: `${idxList}${highRisk.length > 5 ? ' 等' : ''}被判为高疑似（≥70%）。展开对应段落可一键改写。`,
      severity: 'warn',
    })
  }

  if (d.sourceLabels) {
    const entries = Object.entries(d.sourceLabels)
      .filter(([k]) => k !== 'human')
      .sort((a, b) => b[1] - a[1])
    if (entries.length && entries[0][1] >= 0.4) {
      const src = SOURCE_MAP[entries[0][0]]?.label || entries[0][0]
      out.push({
        title: `疑似大量使用 ${src}`,
        body: `${(entries[0][1] * 100).toFixed(0)}% 段落被判为 ${src} 风格。建议避免连续段落使用同一 AI 助手。`,
        severity: 'info',
      })
    }
  }

  if (bodyStats.value && bodyStats.value.excluded > bodyStats.value.body) {
    out.push({
      title: '识别到大量非正文段落',
      body: `${bodyStats.value.excluded} 段被识别为参考文献 / 图表 / 章节标题（未参与 AI 率计算）。若不符合预期请检查论文格式。`,
      severity: 'info',
    })
  }

  return out
})

// severity → 前景/背景/dot 三色（对齐 tokens 语义色）
function sevFg(sev) {
  return sev === 'danger' ? '#C62A22'
    : sev === 'warn' ? '#B26200'
    : sev === 'success' ? '#1B7F3E'
    : '#0056B3'
}
function sevSolid(sev) {
  return sev === 'danger' ? '#FF3B30'
    : sev === 'warn' ? '#FF9500'
    : sev === 'success' ? '#34C759'
    : '#007AFF'
}
function sevBg(sev) {
  return sev === 'danger' ? 'rgba(255,59,48,0.10)'
    : sev === 'warn' ? 'rgba(255,149,0,0.12)'
    : sev === 'success' ? 'rgba(52,199,89,0.10)'
    : 'rgba(0,122,255,0.08)'
}

async function humanize(idx) {
  humanizingMap.value[idx] = true
  try {
    rewrittenMap.value[idx] = await requestHumanize(taskId, idx)
    diffOpenMap.value[idx] = false
  } catch (e) {
    uni.showToast({ title: e?.message || '改写失败', icon: 'none' })
  } finally {
    humanizingMap.value[idx] = false
  }
}
function copyRewritten(idx) {
  const text = rewrittenMap.value[idx]
  if (!text) return
  uni.setClipboardData({
    data: text,
    success: () => uni.showToast({ title: '已复制', icon: 'success' }),
  })
}
function paragraphDiff(idx, original) {
  const rewritten = rewrittenMap.value[idx]
  if (!rewritten) return []
  return diffChars(original, rewritten)
}
function jumpTo(idx) {
  expandedMap.value[idx] = true
  setTimeout(() => { scrollIntoId.value = 'para-' + idx }, 30)
}
function toggleExpand(idx) {
  expandedMap.value[idx] = !expandedMap.value[idx]
}
</script>

<template>
  <Skeleton v-if="loading" :rows="4" />

  <!-- 整页错误态 -->
  <view v-else-if="loadError && !detail" class="error-page">
    <view class="error-mark" />
    <text class="error-title">{{ loadError }}</text>
    <text class="error-sub">请检查任务是否已被删除或稍后重试</text>
    <view class="error-actions">
      <button class="btn-primary" @click="load">重新加载</button>
      <button class="btn-tinted" @click="goBack">返回列表</button>
    </view>
  </view>

  <scroll-view
    v-else-if="detail"
    scroll-y class="page"
    :scroll-into-view="scrollIntoId"
    :scroll-with-animation="true"
  >
    <!-- 处理中 -->
    <view v-if="detail.status === 'RUNNING' || detail.status === 'PENDING'" class="state-card">
      <view class="state-spinner">
        <view class="spinner-ring" />
      </view>
      <text class="state-title" style="color: #B26200">检测中</text>
      <text class="state-sub">页面将自动刷新（约 15-30 秒）</text>
      <button
        class="btn-tinted cancel-btn"
        :loading="cancelling"
        :disabled="cancelling"
        @click="onCancel"
      >取消检测</button>
    </view>

    <!-- 检测失败 -->
    <view v-else-if="detail.status === 'FAILED'" class="state-card">
      <view class="state-mark danger">
        <view class="mark-x-1" />
        <view class="mark-x-2" />
      </view>
      <text class="state-title" style="color: #C62A22">检测失败</text>
      <text class="state-sub">推理服务暂时不可用，可点下方重新提交</text>
      <button
        class="btn-primary retry-btn"
        :loading="retrying"
        :disabled="retrying"
        @click="onRetry"
      >重新检测</button>
    </view>

    <!-- Hero AI 率环 -->
    <view v-else class="hero-card">
      <text class="hero-label">整体 AI 率</text>

      <view class="ring-wrap">
        <svg viewBox="0 0 200 200" class="ring-svg">
          <circle cx="100" cy="100" r="86"
            fill="none" stroke="rgba(120,120,128,0.16)" stroke-width="14"/>
          <circle cx="100" cy="100" r="86"
            fill="none"
            :stroke="summaryColor" stroke-width="14" stroke-linecap="round"
            :stroke-dasharray="ringCircumference"
            :stroke-dashoffset="ringOffset"
            transform="rotate(-90 100 100)"
            style="transition: stroke-dashoffset 900ms cubic-bezier(0.32, 0.72, 0, 1)"/>
          <circle cx="100" cy="100" r="86"
            fill="none"
            :stroke="pass ? '#34C759' : '#FF3B30'"
            stroke-width="14" stroke-linecap="butt"
            :stroke-dasharray="`3 ${ringCircumference - 3}`"
            :stroke-dashoffset="ringThresholdOffset"
            transform="rotate(-90 100 100)" opacity="0.9"/>
        </svg>
        <view class="ring-center">
          <text class="ring-rate" :style="{ color: summaryColor }">
            {{ detail.aiRate?.toFixed(1) }}<text class="ring-unit">%</text>
          </text>
          <text class="ring-cap">红线 ≤ {{ detail.threshold }}%</text>
        </view>
      </view>

      <view class="verdict-pill" :class="pass ? 'verdict-ok' : 'verdict-fail'">
        <text>{{ pass ? '低于红线，达标' : '超过红线 ' + detail.threshold + '%，建议修改' }}</text>
      </view>

      <text v-if="bodyStats" class="hero-hint">
        基于正文 {{ bodyStats.body }} 段计算<template v-if="bodyStats.excluded > 0">，已排除 {{ bodyStats.excluded }} 段（参考文献/图表等）</template>
      </text>
      <text class="hero-paper">{{ detail.paperTitle }}</text>

      <!-- 报告操作 · DONE 状态才出现 -->
      <view v-if="detail.status === 'DONE'" class="report-actions">
        <button
          class="btn-tinted download-btn"
          :loading="downloading"
          :disabled="downloading"
          @click="onDownload"
        >下载 PDF</button>
        <!-- Wave 3.4 · 分享给同学（微信小程序 open-type=share 走 onShareAppMessage）-->
        <!-- #ifdef MP-WEIXIN -->
        <button class="btn-tinted share-btn" open-type="share">分享给同学</button>
        <!-- #endif -->
      </view>
    </view>

    <!-- 改进建议 -->
    <view v-if="suggestions.length" class="section">
      <text class="section-header">改进建议</text>
      <view class="suggest-list">
        <view
          v-for="(s, i) in suggestions" :key="i"
          class="sug-card"
          :style="{ background: sevBg(s.severity) }"
        >
          <view class="sug-dot" :style="{ background: sevSolid(s.severity) }" />
          <view class="sug-body">
            <text class="sug-title" :style="{ color: sevFg(s.severity) }">{{ s.title }}</text>
            <text class="sug-text">{{ s.body }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 溯源分布 -->
    <view v-if="detail.status === 'DONE'" class="section">
      <text class="section-header">疑似来源分布</text>
      <view class="group-card">
        <view v-for="(s, i) in sortedSources" :key="s.label" class="source-item">
          <view class="source-line">
            <view class="source-name-wrap">
              <view class="source-dot" :style="{ background: SOURCE_MAP[s.label]?.color || COLOR.systemGray }" />
              <text class="source-name">{{ SOURCE_MAP[s.label]?.label || s.label }}</text>
            </view>
            <text class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</text>
          </view>
          <view class="bar-track">
            <view class="bar-fill" :style="{ width: (s.ratio * 100) + '%', background: SOURCE_MAP[s.label]?.color || COLOR.systemGray }" />
          </view>
          <view v-if="i < sortedSources.length - 1" class="row-sep" />
        </view>
      </view>
    </view>

    <!-- 段落速览 -->
    <view v-if="detail.status === 'DONE' && (detail.paragraphs || []).length > 1" class="section">
      <text class="section-header">段落速览 · 点击查看</text>
      <view class="group-card overview-card">
        <view class="chip-grid">
          <view
            v-for="p in detail.paragraphs" :key="'ov-' + p.paragraphIdx"
            class="para-chip"
            :style="p.excluded ? {
              color: 'rgba(60,60,67,0.60)',
              background: 'rgba(120,120,128,0.14)'
            } : {
              color: paragraphRisk(p.calibratedProb || 0).color,
              background: paragraphRisk(p.calibratedProb || 0).bg === 'transparent'
                ? 'rgba(52,199,89,0.14)'
                : paragraphRisk(p.calibratedProb || 0).bg
            }"
            hover-class="para-chip-hover"
            @click="jumpTo(p.paragraphIdx)"
          >
            <text class="chip-idx">段 {{ p.paragraphIdx + 1 }}</text>
            <text class="chip-rate">
              {{ p.excluded ? '—' : ((p.calibratedProb || 0) * 100).toFixed(0) + '%' }}
            </text>
          </view>
        </view>
      </view>
    </view>

    <!-- 段落分析 -->
    <view v-if="detail.status === 'DONE'" class="section">
      <view class="section-header-line">
        <text class="section-header no-pad">段落分析</text>
        <view class="legend">
          <view class="legend-item"><view class="swatch high" /><text>高</text></view>
          <view class="legend-item"><view class="swatch mid" /><text>中</text></view>
        </view>
      </view>

      <view
        v-for="p in detail.paragraphs" :key="p.paragraphIdx"
        :id="'para-' + p.paragraphIdx"
        class="para-card group-card"
        :class="{ 'para-excluded': p.excluded }"
      >
        <view class="para-header" hover-class="para-header-hover" @click="toggleExpand(p.paragraphIdx)">
          <view class="para-header-left">
            <text class="para-idx">段 {{ p.paragraphIdx + 1 }}</text>
            <text v-if="p.excluded" class="excluded-badge">
              已排除 · {{ EXCLUDE_REASON_LABEL[p.excludeReason] || '非正文' }}
            </text>
            <text v-else class="para-prob" :style="{ color: paragraphRisk(p.calibratedProb || 0).color }">
              {{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%
              <text v-if="p.sourceLabel && p.sourceLabel !== 'human'" class="para-src">
                · 疑似 {{ SOURCE_MAP[p.sourceLabel]?.label || p.sourceLabel }}
              </text>
            </text>
          </view>
          <text class="chevron" :class="{ expanded: expandedMap[p.paragraphIdx] }">›</text>
        </view>

        <view v-if="!expandedMap[p.paragraphIdx]" class="para-preview">
          {{ (p.text || '').slice(0, 60) }}{{ (p.text || '').length > 60 ? '…' : '' }}
        </view>

        <view v-if="expandedMap[p.paragraphIdx]" class="para-body">
          <view v-if="p.excluded" class="para-excluded-text">{{ p.text }}</view>
          <view v-else class="para-text">
            <text
              v-for="s in p.sentences" :key="s.sentenceIdx"
              :style="{ background: paragraphRisk(s.aiProb).bg }"
            >{{ s.text }}</text>
          </view>

          <button
            v-if="!p.excluded && (p.calibratedProb || 0) >= 0.7 && !rewrittenMap[p.paragraphIdx]"
            class="btn-tinted humanize-btn"
            :loading="humanizingMap[p.paragraphIdx]"
            @click="humanize(p.paragraphIdx)"
          >降 AIGC · 生成改写建议</button>

          <view v-if="rewrittenMap[p.paragraphIdx]" class="rewritten">
            <view class="rewritten-header">
              <text class="rewritten-label">改写建议</text>
              <view class="rewritten-actions">
                <text class="link-btn" @click="diffOpenMap[p.paragraphIdx] = !diffOpenMap[p.paragraphIdx]">
                  {{ diffOpenMap[p.paragraphIdx] ? '隐藏对比' : '看差异' }}
                </text>
                <text class="link-btn primary" @click="copyRewritten(p.paragraphIdx)">复制</text>
              </view>
            </view>
            <view v-if="diffOpenMap[p.paragraphIdx]" class="diff-text">
              <text
                v-for="(seg, i) in paragraphDiff(p.paragraphIdx, p.text)" :key="i"
                :class="'diff-' + seg.type"
              >{{ seg.text }}</text>
            </view>
            <text v-else class="rewritten-text">{{ rewrittenMap[p.paragraphIdx] }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 申诉入口 -->
    <view v-if="detail && detail.status === 'DONE'" class="appeal-card" hover-class="appeal-card-hover" @click="feedbackOpen = true">
      <view class="appeal-icon">
        <view class="appeal-flag-mast" />
        <view class="appeal-flag-cloth" />
      </view>
      <view class="appeal-body">
        <text class="appeal-title">对本次结果有疑问？</text>
        <text class="appeal-sub">提交申诉，我们会人工复核并回复</text>
      </view>
      <text class="appeal-chevron">›</text>
    </view>
  </scroll-view>

  <FeedbackSheet v-model="feedbackOpen" :task-id="Number(taskId) || 0" default-category="appeal" />
</template>

<style lang="scss" scoped>
.page {
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

/* ============ 整页错误 ============ */
.error-page {
  min-height: 100vh;
  padding: 200rpx $sp-6;
  display: flex; flex-direction: column; align-items: center;
  background: $bg-grouped-primary;
}
.error-mark {
  width: 96rpx; height: 96rpx; border-radius: 50%;
  background: $danger-bg;
  position: relative;
  margin-bottom: $sp-5;
  &::before {
    content: '!';
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 56rpx; font-weight: $fw-bold; color: $danger-solid;
    font-family: $font-family;
  }
}
.error-title {
  font-size: $fs-title-3; font-weight: $fw-semibold;
  color: $label-primary; letter-spacing: $tracking-snug;
}
.error-sub {
  font-size: $fs-subhead; color: $label-secondary;
  margin-top: $sp-2; text-align: center;
}
.error-actions {
  display: flex; gap: $sp-3;
  margin-top: $sp-8; width: 100%; justify-content: center;
}

/* ============ 状态卡（处理中 / 失败） ============ */
.state-card {
  @include card;
  padding: 80rpx $sp-5 60rpx;
  text-align: center;
  display: flex; flex-direction: column; align-items: center;
}
.state-title {
  display: block;
  font-size: $fs-title-3; font-weight: $fw-semibold;
  letter-spacing: $tracking-snug;
  margin-top: $sp-4;
}
.state-sub {
  display: block;
  font-size: $fs-subhead; color: $label-secondary;
  margin-top: $sp-2;
}

/* CSS 环形 spinner（替代 ⏳ emoji） */
.state-spinner {
  width: 96rpx; height: 96rpx; position: relative;
}
.spinner-ring {
  width: 100%; height: 100%;
  border-radius: 50%;
  border: 8rpx solid rgba(255, 149, 0, 0.18);
  border-top-color: $warning-solid;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* CSS X 标（替代 ❌ emoji） */
.state-mark {
  width: 96rpx; height: 96rpx; border-radius: 50%;
  position: relative;
  &.danger { background: $danger-bg; }
}
.mark-x-1, .mark-x-2 {
  position: absolute;
  left: 20%; right: 20%; top: 48%;
  height: 6rpx; border-radius: 3rpx;
  background: $danger-solid;
  transform-origin: center;
}
.mark-x-1 { transform: rotate(45deg); }
.mark-x-2 { transform: rotate(-45deg); }

.retry-btn { margin-top: $sp-5; min-width: 320rpx; }
.cancel-btn { margin-top: $sp-5; min-width: 320rpx; }
.report-actions {
  margin-top: $sp-4;
  display: flex;
  gap: $sp-2;
  justify-content: center;
  flex-wrap: wrap;
}
.download-btn, .share-btn {
  min-width: 220rpx;
  flex: 0 1 auto;
}

/* ============ 主 & 次 按钮 ============ */
.btn-primary {
  min-width: 240rpx;
  height: $size-btn-h-lg; line-height: $size-btn-h-lg;
  background: $brand-primary; color: #FFFFFF;
  font-size: $fs-headline; font-weight: $fw-semibold;
  border-radius: $radius-pill;
  transition: transform $duration-fast $ease-standard, background $duration-fast;
  &:active { transform: scale(#{$tap-scale}); background: $brand-primary-tint; }
  &[disabled] { opacity: 0.5; }
}
.btn-tinted {
  min-width: 240rpx;
  height: $size-btn-h-lg; line-height: $size-btn-h-lg;
  background: $brand-primary-wash; color: $brand-primary;
  font-size: $fs-body; font-weight: $fw-semibold;
  border-radius: $radius-pill;
  transition: opacity $duration-fast;
  &:active { opacity: 0.7; }
}

/* ============ Hero AI 率环 ============ */
.hero-card {
  @include card;
  padding: 56rpx $sp-5 48rpx;
  text-align: center;
  display: flex; flex-direction: column; align-items: center;
}
.hero-label {
  display: block;
  font-size: $fs-footnote; font-weight: $fw-medium;
  color: $label-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wide;
}
.ring-wrap {
  position: relative;
  width: 440rpx; height: 440rpx;
  margin: $sp-4 auto $sp-3;
}
.ring-svg { width: 440rpx; height: 440rpx; display: block; }
.ring-center {
  position: absolute; inset: 0;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.ring-rate {
  font-size: 100rpx; font-weight: $fw-bold;
  letter-spacing: -2rpx; line-height: 1;
  font-variant-numeric: tabular-nums;
}
.ring-unit {
  font-size: 40rpx; font-weight: $fw-semibold;
  color: $label-secondary;
  margin-left: 4rpx;
}
.ring-cap {
  display: block;
  font-size: $fs-caption-1; color: $label-secondary;
  margin-top: $sp-2; letter-spacing: 1rpx;
}
.verdict-pill {
  display: inline-flex; align-items: center;
  padding: $sp-2 $sp-4;
  border-radius: $radius-pill;
  font-size: $fs-subhead; font-weight: $fw-semibold;
  &.verdict-ok   { background: $success-bg; color: $success-fg; }
  &.verdict-fail { background: $danger-bg;  color: $danger-fg;  }
}
.hero-hint {
  display: block;
  font-size: $fs-caption-1; color: $label-secondary;
  margin-top: $sp-3; padding: 0 $sp-3;
  line-height: $lh-normal;
}
.hero-paper {
  display: block;
  font-size: $fs-footnote; color: $label-secondary;
  margin-top: $sp-4; padding-top: $sp-3;
  border-top: $stroke-hairline solid $separator;
}

/* ============ Section 通用 ============ */
.section { margin-top: $sp-6; }
.section-header {
  display: block;
  padding: 0 $sp-3 $sp-2;
  font-size: $fs-footnote; font-weight: $fw-medium;
  color: $label-secondary;
  text-transform: uppercase; letter-spacing: $tracking-wide;
  &.no-pad { padding-left: 0; }
}
.section-header-line {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 $sp-3 $sp-2;
}
.legend { display: inline-flex; gap: $sp-3; font-size: $fs-caption-2; color: $label-secondary; }
.legend-item { display: inline-flex; align-items: center; gap: 6rpx; }
.swatch { display: inline-block; width: 24rpx; height: 12rpx; border-radius: 4rpx; }
.swatch.high { background: rgba(255, 59, 48, 0.30); }
.swatch.mid  { background: rgba(255, 149, 0, 0.30); }

.group-card { @include card-flush; }

/* ============ 改进建议 ============ */
.suggest-list { display: flex; flex-direction: column; gap: $sp-2; }
.sug-card {
  border-radius: $radius-lg;
  padding: $sp-3 $sp-3 $sp-3 $sp-2;
  display: flex; gap: $sp-3; align-items: flex-start;
}
.sug-dot {
  width: 12rpx; height: 12rpx; border-radius: 50%;
  margin-top: 14rpx; flex-shrink: 0;
}
.sug-body { flex: 1; }
.sug-title {
  display: block;
  font-size: $fs-headline; font-weight: $fw-semibold;
  letter-spacing: $tracking-snug;
  margin-bottom: 6rpx;
}
.sug-text {
  display: block;
  font-size: $fs-subhead; color: $label-primary; opacity: 0.85;
  line-height: $lh-normal;
}

/* ============ 溯源分布 ============ */
.source-item { padding: $sp-4 $sp-4; position: relative; }
.source-line {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: $sp-2;
}
.source-name-wrap { display: inline-flex; align-items: center; }
.source-dot { width: 20rpx; height: 20rpx; border-radius: 50%; margin-right: $sp-2; }
.source-name { font-size: $fs-subhead; color: $label-primary; font-weight: $fw-medium; }
.source-ratio {
  font-size: $fs-callout; color: $label-primary;
  font-weight: $fw-semibold; font-variant-numeric: tabular-nums;
}
.bar-track {
  height: 10rpx;
  background: $fill-tertiary;
  border-radius: 5rpx; overflow: hidden;
}
.bar-fill {
  height: 100%; border-radius: 5rpx;
  transition: width $duration-slow $ease-standard;
}
.row-sep {
  position: absolute; left: $sp-4; right: 0; bottom: 0;
  height: $stroke-hairline; background: $separator;
}

/* ============ 段落速览 chip grid ============ */
.overview-card { padding: $sp-3 $sp-2 $sp-1; }
.chip-grid {
  display: flex; flex-wrap: wrap; gap: $sp-2;
}
.para-chip {
  min-width: 130rpx;
  padding: $sp-2 $sp-3;
  border-radius: $radius-md;
  display: flex; flex-direction: column; align-items: center;
  transition: transform $duration-fast $ease-standard;
}
.para-chip-hover { transform: scale(0.94); }
.chip-idx {
  font-size: $fs-caption-2; font-weight: $fw-semibold;
  opacity: 0.85; letter-spacing: 0.5rpx;
}
.chip-rate {
  font-size: $fs-callout; font-weight: $fw-bold;
  font-variant-numeric: tabular-nums;
  margin-top: 4rpx; letter-spacing: -0.5rpx;
}

/* ============ 段落卡 ============ */
.para-card {
  margin-bottom: $sp-2;
  padding: 0;
  overflow: hidden;
  transition: background $duration-fast;
}
.para-excluded { opacity: 0.7; }
.para-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: $sp-3 $sp-4;
  transition: background $duration-fast $ease-standard;
}
.para-header-hover { background: rgba(60, 60, 67, 0.06); }
.para-header-left {
  display: flex; align-items: baseline; gap: $sp-2;
  flex: 1; min-width: 0;
}
.para-idx {
  font-size: $fs-caption-2; color: $label-secondary;
  font-weight: $fw-semibold; letter-spacing: 1rpx;
  text-transform: uppercase;
}
.para-prob { font-size: $fs-subhead; font-weight: $fw-semibold; }
.para-src  { color: $label-secondary; font-weight: $fw-regular; }
.excluded-badge {
  font-size: $fs-caption-2; color: $label-secondary;
  background: $fill-tertiary;
  padding: 4rpx 16rpx; border-radius: $radius-pill;
  font-weight: $fw-medium;
}
.chevron {
  font-size: 40rpx; color: $label-tertiary; line-height: 1;
  transition: transform $duration-base $ease-standard;
}
.chevron.expanded { transform: rotate(90deg); }

.para-preview {
  padding: 0 $sp-4 $sp-3;
  font-size: $fs-subhead; line-height: $lh-normal;
  color: $label-secondary;
}
.para-body {
  padding: $sp-3 $sp-4 $sp-4;
  border-top: $stroke-hairline solid $label-quaternary;
}
.para-text { font-size: $fs-body; line-height: $lh-relaxed; color: $label-primary; }
.para-excluded-text { font-size: $fs-callout; line-height: $lh-normal; color: $label-secondary; }

.humanize-btn {
  margin-top: $sp-3;
  width: 100%;
  height: $size-btn-h-md; line-height: $size-btn-h-md;
  border-radius: $radius-btn;
}

/* ============ 改写卡 ============ */
.rewritten {
  margin-top: $sp-3;
  background: $brand-primary-wash;
  border-radius: $radius-md;
  padding: $sp-3 $sp-4;
}
.rewritten-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: $sp-2;
}
.rewritten-label {
  font-size: $fs-caption-1; color: $brand-primary;
  font-weight: $fw-semibold; letter-spacing: 0.5rpx;
}
.rewritten-actions { display: flex; gap: $sp-3; }
.link-btn {
  font-size: $fs-footnote; color: $brand-primary;
  font-weight: $fw-medium;
  padding: 4rpx 16rpx;
  border-radius: $radius-pill;
  border: $stroke-hairline solid $brand-primary;
  &.primary { background: $brand-primary; color: #FFFFFF; border-color: $brand-primary; }
}
.rewritten-text { font-size: $fs-callout; line-height: $lh-relaxed; color: $label-primary; }

/* diff */
.diff-text { font-size: $fs-callout; line-height: $lh-relaxed; }
.diff-equal  { color: $label-primary; }
.diff-add    { background: rgba(52, 199, 89, 0.20); color: $success-fg; }
.diff-remove { background: rgba(255, 59, 48, 0.16); color: $danger-fg; text-decoration: line-through; }

/* ============ 申诉入口卡（CSS 小旗 icon 替代 emoji 🚩） ============ */
.appeal-card {
  margin: $sp-4 0 0;
  padding: $sp-3 $sp-4;
  background: $bg-primary;
  border-radius: $radius-lg;
  box-shadow: $shadow-card;
  display: flex; align-items: center;
  transition: background $duration-fast;
}
.appeal-card-hover { background: rgba(60, 60, 67, 0.05); }
.appeal-icon {
  position: relative;
  width: 48rpx; height: 48rpx; margin-right: $sp-3;
  flex-shrink: 0;
}
.appeal-flag-mast {
  position: absolute; left: 12rpx; top: 4rpx;
  width: 4rpx; height: 40rpx;
  background: $label-primary;
  border-radius: 2rpx;
}
.appeal-flag-cloth {
  position: absolute; left: 16rpx; top: 4rpx;
  width: 26rpx; height: 20rpx;
  background: $brand-primary;
  clip-path: polygon(0 0, 100% 0, 70% 50%, 100% 100%, 0 100%);
}
.appeal-body { flex: 1; }
.appeal-title { display: block; font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.appeal-sub { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-top: 6rpx; }
.appeal-chevron { color: $label-tertiary; font-size: 36rpx; margin-left: $sp-2; }
</style>
