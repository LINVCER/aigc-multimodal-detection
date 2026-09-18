<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getTaskDetail, requestHumanize, retryTask } from '@/api/detect'
import { SOURCE_MAP, COLOR, paragraphRisk, aiRateColor } from '@/utils/constants'
import { diffChars } from '@/utils/diff'
import Skeleton from '@/components/Skeleton.vue'

const detail = ref(null)
const loading = ref(true)
const loadError = ref('')      // 加载失败（404 / 网络异常）触发兜底 UI
const retrying = ref(false)
const rewrittenMap = ref({})
const humanizingMap = ref({})
const diffOpenMap = ref({})
const expandedMap = ref({})    // 段落卡默认折叠，点击展开
const scrollIntoId = ref('')   // scroll-view 定位锚点，速览点击后设置
let pollTimer = null
let taskId = null

async function load() {
  loadError.value = ''
  try {
    detail.value = await getTaskDetail(taskId)
  } catch (e) {
    loadError.value = e?.message || '加载失败'
  } finally {
    loading.value = false
  }
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

async function onRetry() {
  retrying.value = true
  try {
    await retryTask(taskId)
    uni.showToast({ title: '已重新提交', icon: 'success' })
    await load()
    ensurePolling()
  } catch (e) {
    uni.showToast({ title: e?.message || '重试失败', icon: 'none' })
  } finally {
    retrying.value = false
  }
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

const sortedSources = computed(() => {
  if (!detail.value?.sourceLabels) return []
  return Object.entries(detail.value.sourceLabels)
    .sort((a, b) => b[1] - a[1])
    .map(([label, ratio]) => ({ label, ratio }))
})

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

/**
 * 点段落速览 chip：展开对应段 + 滚动定位
 */
function jumpTo(idx) {
  expandedMap.value[idx] = true
  // 微延迟保证 DOM 展开完成后再触发 scroll-into-view
  setTimeout(() => { scrollIntoId.value = 'para-' + idx }, 30)
}

function toggleExpand(idx) {
  expandedMap.value[idx] = !expandedMap.value[idx]
}
</script>

<template>
  <Skeleton v-if="loading" :rows="4" />

  <!-- 加载失败兜底（404 / 网络异常 / 无效任务号）-->
  <view v-else-if="loadError && !detail" class="error-page">
    <text class="error-icon">⚠️</text>
    <text class="error-title">{{ loadError }}</text>
    <text class="error-sub">请检查任务是否已被删除或稍后重试</text>
    <view class="error-actions">
      <button class="error-btn primary" @click="load">重新加载</button>
      <button class="error-btn" @click="goBack">返回列表</button>
    </view>
  </view>

  <scroll-view
    v-else-if="detail"
    scroll-y class="page"
    :scroll-into-view="scrollIntoId"
    :scroll-with-animation="true"
  >
    <!-- 处理中 -->
    <view v-if="detail.status === 'RUNNING' || detail.status === 'PENDING'" class="processing group-card">
      <text class="processing-icon">⏳</text>
      <text class="processing-title">检测中</text>
      <text class="processing-sub">页面将自动刷新（约 15-30 秒）</text>
    </view>

    <!-- 检测失败 -->
    <view v-else-if="detail.status === 'FAILED'" class="failed-card group-card">
      <text class="failed-icon">❌</text>
      <text class="failed-title">检测失败</text>
      <text class="failed-sub">推理服务暂时不可用，可点下方重新提交</text>
      <button
        class="retry-btn"
        :loading="retrying"
        :disabled="retrying"
        @click="onRetry"
      >重新检测</button>
    </view>

    <!-- 总览大数字（Health app 风） -->
    <view v-else class="summary-hero">
      <text class="summary-label">整体 AI 率</text>
      <view class="summary-rate-line">
        <text class="summary-rate" :style="{ color: summaryColor }">{{ detail.aiRate?.toFixed(1) }}</text>
        <text class="summary-unit">%</text>
      </view>
      <text class="summary-verdict" :style="{ color: summaryColor }">
        {{ pass ? '低于红线 ' + detail.threshold + '%，达标' : '超过红线 ' + detail.threshold + '%，建议修改' }}
      </text>
      <text class="summary-paper">{{ detail.paperTitle }}</text>
    </view>

    <!-- 溯源分布 -->
    <view v-if="detail.status === 'DONE'" class="section">
      <text class="section-header">疑似来源分布</text>
      <view class="group-card">
        <view v-for="(s, i) in sortedSources" :key="s.label" class="source-item">
          <view class="source-line">
            <view class="source-name-wrap">
              <view class="source-dot" :style="{ background: SOURCE_MAP[s.label]?.color || COLOR.systemGray }"></view>
              <text class="source-name">{{ SOURCE_MAP[s.label]?.label || s.label }}</text>
            </view>
            <text class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</text>
          </view>
          <view class="bar-track">
            <view class="bar-fill" :style="{ width: (s.ratio * 100) + '%', background: SOURCE_MAP[s.label]?.color || COLOR.systemGray }"></view>
          </view>
          <view v-if="i < sortedSources.length - 1" class="source-sep"></view>
        </view>
      </view>
    </view>

    <!-- 段落速览：一屏定位所有段的 AI 率，chip 点击展开+滚动到该段 -->
    <view v-if="detail.status === 'DONE' && (detail.paragraphs || []).length > 1" class="section">
      <text class="section-header">段落速览 · 点击查看</text>
      <view class="group-card overview-card">
        <view class="chip-grid">
          <view
            v-for="p in detail.paragraphs" :key="'ov-' + p.paragraphIdx"
            class="para-chip"
            :style="{
              color: paragraphRisk(p.calibratedProb).color,
              background: paragraphRisk(p.calibratedProb).bg === 'transparent'
                ? 'rgba(52,199,89,0.14)'
                : paragraphRisk(p.calibratedProb).bg
            }"
            hover-class="para-chip-hover"
            @click="jumpTo(p.paragraphIdx)"
          >
            <text class="chip-idx">段 {{ p.paragraphIdx + 1 }}</text>
            <text class="chip-rate">{{ (p.calibratedProb * 100).toFixed(0) }}%</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 段落列表 -->
    <view v-if="detail.status === 'DONE'" class="section">
      <view class="section-header-line">
        <text class="section-header">段落分析</text>
        <view class="legend">
          <text><text class="swatch high"></text> 高</text>
          <text><text class="swatch mid"></text> 中</text>
        </view>
      </view>

      <view
        v-for="p in detail.paragraphs" :key="p.paragraphIdx"
        :id="'para-' + p.paragraphIdx"
        class="para-card group-card"
      >
        <!-- 折叠头：全宽点击区，右侧 chevron -->
        <view class="para-header" hover-class="para-header-hover" @click="toggleExpand(p.paragraphIdx)">
          <view class="para-header-left">
            <text class="para-idx">段 {{ p.paragraphIdx + 1 }}</text>
            <text class="para-prob" :style="{ color: paragraphRisk(p.calibratedProb).color }">
              {{ (p.calibratedProb * 100).toFixed(0) }}%
              <text v-if="p.sourceLabel && p.sourceLabel !== 'human'">
                · 疑似 {{ SOURCE_MAP[p.sourceLabel]?.label || p.sourceLabel }}
              </text>
            </text>
          </view>
          <text class="chevron" :class="{ expanded: expandedMap[p.paragraphIdx] }">›</text>
        </view>

        <!-- 折叠体：默认展示前 60 字预览 + 三档色高亮；展开后完整段落 -->
        <view v-if="!expandedMap[p.paragraphIdx]" class="para-preview">
          {{ (p.text || '').slice(0, 60) }}{{ (p.text || '').length > 60 ? '…' : '' }}
        </view>

        <view v-if="expandedMap[p.paragraphIdx]" class="para-body">
          <view class="para-text">
            <text
              v-for="s in p.sentences" :key="s.sentenceIdx"
              :style="{ background: paragraphRisk(s.aiProb).bg }"
            >{{ s.text }}</text>
          </view>

          <!-- 高危：改写 -->
          <button
            v-if="p.calibratedProb >= 0.7 && !rewrittenMap[p.paragraphIdx]"
            class="tinted-btn"
            :loading="humanizingMap[p.paragraphIdx]"
            @click="humanize(p.paragraphIdx)"
          >✨  降 AIGC 改写建议</button>

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
  </scroll-view>
</template>

<style lang="scss" scoped>
.page { padding: 24rpx 32rpx 100rpx; background: #F2F2F7; }

/* 处理中 */
.processing {
  padding: 80rpx 40rpx !important;
  text-align: center;
}
.processing-icon { font-size: 96rpx; display: block; margin-bottom: 24rpx; }
.processing-title { display: block; font-size: 40rpx; font-weight: 600; color: #FF9500; }
.processing-sub { display: block; font-size: 28rpx; color: rgba(60,60,67,0.60); margin-top: 12rpx; }

/* 检测失败 */
.failed-card {
  padding: 80rpx 40rpx 60rpx !important;
  text-align: center;
}
.failed-icon { font-size: 96rpx; display: block; margin-bottom: 24rpx; }
.failed-title { display: block; font-size: 40rpx; font-weight: 600; color: #FF3B30; }
.failed-sub { display: block; font-size: 28rpx; color: rgba(60,60,67,0.60); margin-top: 12rpx; }
.retry-btn {
  margin-top: 40rpx;
  min-width: 300rpx;
  height: 88rpx;
  line-height: 88rpx;
  background: #007AFF;
  color: #FFFFFF;
  font-size: 32rpx;
  font-weight: 600;
  border-radius: 9999rpx;
  transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1);
  &:active { transform: scale(0.96); }
  &[disabled] { opacity: 0.5; }
}

/* 加载失败兜底（整页错误态）*/
.error-page {
  min-height: 100vh;
  padding: 200rpx 60rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #F2F2F7;
}
.error-icon { font-size: 128rpx; margin-bottom: 40rpx; }
.error-title { font-size: 40rpx; font-weight: 600; color: #000; letter-spacing: -0.5rpx; }
.error-sub {
  font-size: 28rpx; color: rgba(60,60,67,0.60);
  margin-top: 16rpx; text-align: center;
}
.error-actions {
  display: flex; gap: 24rpx;
  margin-top: 60rpx;
  width: 100%; justify-content: center;
}
.error-btn {
  min-width: 240rpx;
  height: 88rpx;
  line-height: 88rpx;
  background: rgba(0,122,255,0.10);
  color: #007AFF;
  font-size: 30rpx;
  font-weight: 600;
  border-radius: 9999rpx;
  transition: background 200ms;
  &.primary { background: #007AFF; color: #fff; }
  &:active { opacity: 0.85; }
}

/* Hero 大数字（Fitness app 风） */
.summary-hero {
  background: #FFFFFF;
  border-radius: 28rpx;
  padding: 56rpx 40rpx 48rpx;
  text-align: center;
}
.summary-label {
  display: block;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(60,60,67,0.60);
  text-transform: uppercase;
  letter-spacing: 1rpx;
}
.summary-rate-line {
  display: inline-flex;
  align-items: baseline;
  margin: 20rpx 0 16rpx;
}
.summary-rate {
  font-size: 176rpx;
  font-weight: 700;
  letter-spacing: -4rpx;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.summary-unit {
  font-size: 60rpx;
  font-weight: 600;
  margin-left: 8rpx;
  color: rgba(60,60,67,0.60);
}
.summary-verdict {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
}
.summary-paper {
  display: block;
  font-size: 26rpx;
  color: rgba(60,60,67,0.60);
  margin-top: 32rpx;
  padding-top: 24rpx;
  border-top: 1rpx solid rgba(60,60,67,0.18);
}

/* Sections */
.section { margin-top: 48rpx; }
.section-header {
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(60,60,67,0.60);
  text-transform: uppercase;
  letter-spacing: 1rpx;
  padding: 0 20rpx 12rpx;
  display: block;
}
.section-header-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-right: 20rpx;
}
.legend {
  font-size: 22rpx;
  color: rgba(60,60,67,0.60);
  display: inline-flex; gap: 20rpx;
}
.swatch { display: inline-block; width: 24rpx; height: 12rpx; border-radius: 4rpx; margin-right: 6rpx; vertical-align: middle; }
.swatch.high { background: rgba(255,59,48,0.30); }
.swatch.mid  { background: rgba(255,149,0,0.30); }

.group-card {
  background: #FFFFFF;
  border-radius: 28rpx;
  overflow: hidden;
}

/* Source list */
.source-item { padding: 28rpx 32rpx; position: relative; }
.source-line {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 12rpx;
}
.source-name-wrap { display: inline-flex; align-items: center; }
.source-dot { width: 20rpx; height: 20rpx; border-radius: 50%; margin-right: 16rpx; }
.source-name { font-size: 30rpx; color: #000; font-weight: 500; }
.source-ratio { font-size: 28rpx; color: #000; font-weight: 600; font-variant-numeric: tabular-nums; }
.bar-track {
  height: 10rpx;
  background: rgba(120,120,128,0.16);
  border-radius: 5rpx;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  border-radius: 5rpx;
  transition: width 400ms cubic-bezier(0.32, 0.72, 0, 1);
}
.source-sep {
  position: absolute;
  left: 32rpx; right: 0; bottom: 0;
  height: 1rpx;
  background: rgba(60,60,67,0.18);
}

/* 段落速览 chip grid */
.overview-card { padding: 24rpx 20rpx 12rpx !important; }
.chip-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}
.para-chip {
  min-width: 130rpx;
  padding: 16rpx 24rpx;
  border-radius: 20rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1);
}
.para-chip-hover { transform: scale(0.94); }
.chip-idx {
  font-size: 20rpx;
  font-weight: 600;
  opacity: 0.85;
  letter-spacing: 0.5rpx;
  text-transform: uppercase;
}
.chip-rate {
  font-size: 32rpx;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 4rpx;
  letter-spacing: -0.5rpx;
}

/* Para cards */
.para-card {
  margin-bottom: 20rpx;
  padding: 0;                /* 交给 header/body 各自 padding，方便点击展开动画 */
  overflow: hidden;
}
.para-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 28rpx 32rpx;
  transition: background 150ms;
}
.para-header-hover { background: rgba(60,60,67,0.06); }
.para-header-left { display: flex; align-items: baseline; gap: 20rpx; }
.para-idx { font-size: 22rpx; color: rgba(60,60,67,0.60); font-weight: 600; letter-spacing: 1rpx; text-transform: uppercase; }
.para-prob { font-size: 26rpx; font-weight: 600; }
.chevron {
  font-size: 40rpx;
  color: rgba(60,60,67,0.30);
  line-height: 1;
  transition: transform 300ms cubic-bezier(0.32, 0.72, 0, 1);
  transform: rotate(0deg);
}
.chevron.expanded { transform: rotate(90deg); }

.para-preview {
  padding: 0 32rpx 28rpx;
  font-size: 28rpx;
  line-height: 1.5;
  color: rgba(60,60,67,0.60);
}

.para-body {
  padding: 8rpx 32rpx 32rpx;
  border-top: 1rpx solid rgba(60,60,67,0.10);
  padding-top: 24rpx;
}
.para-text { font-size: 32rpx; line-height: 1.7; color: #000; }

/* Tinted 按钮（iOS Tinted style） */
.tinted-btn {
  margin-top: 24rpx;
  background: rgba(0,122,255,0.12);
  color: #007AFF;
  font-size: 30rpx;
  font-weight: 600;
  border-radius: 20rpx;
  padding: 22rpx 0;
  transition: background 200ms;
  &:active { background: rgba(0,122,255,0.22); }
}

/* 改写卡 */
.rewritten {
  margin-top: 24rpx;
  background: rgba(0,122,255,0.06);
  border-radius: 20rpx;
  padding: 28rpx;
}
.rewritten-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 16rpx;
}
.rewritten-label { font-size: 24rpx; color: #007AFF; font-weight: 600; letter-spacing: 0.5rpx; }
.rewritten-actions { display: flex; gap: 24rpx; }
.link-btn {
  font-size: 26rpx;
  color: #007AFF;
  font-weight: 500;
  padding: 4rpx 16rpx;
  border-radius: 9999rpx;
  border: 1rpx solid #007AFF;
  &.primary { background: #007AFF; color: #fff; }
}
.rewritten-text { font-size: 30rpx; line-height: 1.7; color: #000; }

/* diff */
.diff-text { font-size: 30rpx; line-height: 1.7; }
.diff-equal  { color: #000; }
.diff-add    { background: rgba(52,199,89,0.20); color: #1B7F3E; }
.diff-remove { background: rgba(255,59,48,0.16); color: #C62A22; text-decoration: line-through; }
</style>
