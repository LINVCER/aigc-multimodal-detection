<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getTaskDetail, requestHumanize } from '@/api/detect'
import { SOURCE_MAP, COLOR, paragraphRisk, aiRateColor } from '@/utils/constants'
import { diffChars } from '@/utils/diff'
import Skeleton from '@/components/Skeleton.vue'

const detail = ref(null)
const loading = ref(true)
const rewrittenMap = ref({})
const humanizingMap = ref({})
const diffOpenMap = ref({})
let pollTimer = null
let taskId = null

async function load() {
  try {
    detail.value = await getTaskDetail(taskId)
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

onLoad(async (query) => {
  taskId = Number(query.id)
  await load()
  if (detail.value && (detail.value.status === 'PENDING' || detail.value.status === 'RUNNING')) {
    pollTimer = setInterval(async () => {
      await load()
      if (detail.value.status === 'DONE' || detail.value.status === 'FAILED') stopPoll()
    }, 3000)
  }
})

function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
onUnmounted(stopPoll)

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
</script>

<template>
  <Skeleton v-if="loading" :rows="4" />

  <scroll-view v-else-if="detail" scroll-y class="page">
    <!-- 处理中 -->
    <view v-if="detail.status === 'RUNNING' || detail.status === 'PENDING'" class="processing group-card">
      <text class="processing-icon">⏳</text>
      <text class="processing-title">检测中</text>
      <text class="processing-sub">页面将自动刷新（约 15-30 秒）</text>
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

    <!-- 段落列表 -->
    <view v-if="detail.status === 'DONE'" class="section">
      <view class="section-header-line">
        <text class="section-header">段落分析</text>
        <view class="legend">
          <text><text class="swatch high"></text> 高</text>
          <text><text class="swatch mid"></text> 中</text>
        </view>
      </view>

      <view v-for="p in detail.paragraphs" :key="p.paragraphIdx" class="para-card group-card">
        <view class="para-header">
          <text class="para-idx">段 {{ p.paragraphIdx + 1 }}</text>
          <text class="para-prob" :style="{ color: paragraphRisk(p.calibratedProb).color }">
            {{ (p.calibratedProb * 100).toFixed(0) }}%
            <text v-if="p.sourceLabel && p.sourceLabel !== 'human'">
              · 疑似 {{ SOURCE_MAP[p.sourceLabel]?.label || p.sourceLabel }}
            </text>
          </text>
        </view>

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

/* Para cards */
.para-card {
  margin-bottom: 20rpx;
  padding: 32rpx;
}
.para-header {
  display: flex; justify-content: space-between;
  margin-bottom: 20rpx;
}
.para-idx { font-size: 22rpx; color: rgba(60,60,67,0.60); font-weight: 600; letter-spacing: 1rpx; text-transform: uppercase; }
.para-prob { font-size: 24rpx; font-weight: 600; }
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
