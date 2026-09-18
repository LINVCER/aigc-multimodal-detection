<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { getTaskDetail, requestHumanize } from '@/api/detect'
import { SOURCE_MAP, paragraphRisk, aiRateColor } from '@/utils/constants'
import { diffChars } from '@/utils/diff'
import AiRateBadge from '@/components/AiRateBadge.vue'
import Skeleton from '@/components/Skeleton.vue'

const detail = ref(null)
const loading = ref(true)
const rewrittenMap = ref({})       // { paragraphIdx: text }
const humanizingMap = ref({})      // { paragraphIdx: bool }
const diffOpenMap = ref({})        // { paragraphIdx: bool }
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
  // 处理中的任务：每 3s 轮询一次直到 DONE/FAILED
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
    diffOpenMap.value[idx] = false      // 默认收起 diff
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

/**
 * 段落 diff：返回 [{type, text}] 三色数组，供模板渲染
 */
function paragraphDiff(idx, original) {
  const rewritten = rewrittenMap.value[idx]
  if (!rewritten) return []
  return diffChars(original, rewritten)
}
</script>

<template>
  <Skeleton v-if="loading" :rows="4" />

  <scroll-view v-else-if="detail" scroll-y class="page">
    <!-- 处理中的进度提示 -->
    <view v-if="detail.status === 'RUNNING' || detail.status === 'PENDING'" class="processing">
      <text class="processing-icon">⏳</text>
      <text class="processing-text">检测中，页面将自动刷新（约 15-30 秒）</text>
    </view>

    <!-- 总览卡 -->
    <view v-else class="summary" :style="{ background: pass ? '#ecfdf5' : '#fef2f2' }">
      <text class="summary-title">{{ detail.paperTitle }}</text>
      <AiRateBadge :rate="detail.aiRate" :threshold="detail.threshold" size="lg" />
      <text class="summary-verdict" :style="{ color: summaryColor }">
        {{ pass ? `✓ 低于红线 ${detail.threshold}%，达标` : `⚠ 超过红线 ${detail.threshold}%，建议修改` }}
      </text>
    </view>

    <!-- 溯源分布 -->
    <view v-if="detail.status === 'DONE'" class="card">
      <text class="card-title">疑似来源分布</text>
      <view v-for="s in sortedSources" :key="s.label" class="source-row">
        <text class="source-label">{{ SOURCE_MAP[s.label]?.label || s.label }}</text>
        <view class="bar-track">
          <view
            class="bar-fill"
            :style="{ width: (s.ratio * 100) + '%', background: SOURCE_MAP[s.label]?.color || '#9ca3af' }"
          ></view>
        </view>
        <text class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</text>
      </view>
    </view>

    <!-- 图例 -->
    <view v-if="detail.status === 'DONE'" class="legend">
      <text class="legend-item"><text class="swatch high">　</text> 高疑似</text>
      <text class="legend-item"><text class="swatch mid">　</text> 中等</text>
      <text class="legend-item">无底色 = 人写</text>
    </view>

    <!-- 段落列表 -->
    <view v-if="detail.status === 'DONE'" v-for="p in detail.paragraphs" :key="p.paragraphIdx" class="para">
      <view class="para-header">
        <text class="para-idx">第 {{ p.paragraphIdx + 1 }} 段</text>
        <text class="para-prob" :style="{ color: paragraphRisk(p.calibratedProb).color }">
          {{ (p.calibratedProb * 100).toFixed(0) }}%
          <text v-if="p.sourceLabel && p.sourceLabel !== 'human'">
            · 疑似 {{ SOURCE_MAP[p.sourceLabel]?.label || p.sourceLabel }}
          </text>
        </text>
      </view>

      <!-- 句子级高亮原文 -->
      <view class="para-text">
        <text
          v-for="s in p.sentences" :key="s.sentenceIdx"
          :style="{ background: paragraphRisk(s.aiProb).bg }"
        >{{ s.text }}</text>
      </view>

      <!-- 高危：改写按钮 / 结果 -->
      <button
        v-if="p.calibratedProb >= 0.7 && !rewrittenMap[p.paragraphIdx]"
        class="humanize-btn"
        :loading="humanizingMap[p.paragraphIdx]"
        @click="humanize(p.paragraphIdx)"
      >✨ 降 AIGC 改写建议</button>

      <view v-if="rewrittenMap[p.paragraphIdx]" class="rewritten">
        <view class="rewritten-header">
          <text class="rewritten-label">改写建议</text>
          <view class="rewritten-actions">
            <text class="rewritten-btn" @click="diffOpenMap[p.paragraphIdx] = !diffOpenMap[p.paragraphIdx]">
              {{ diffOpenMap[p.paragraphIdx] ? '隐藏对比' : '看差异' }}
            </text>
            <text class="rewritten-btn primary" @click="copyRewritten(p.paragraphIdx)">复制</text>
          </view>
        </view>

        <!-- diff 视图 -->
        <view v-if="diffOpenMap[p.paragraphIdx]" class="diff-text">
          <text
            v-for="(seg, i) in paragraphDiff(p.paragraphIdx, p.text)" :key="i"
            :class="'diff-' + seg.type"
          >{{ seg.text }}</text>
        </view>
        <text v-else class="rewritten-text">{{ rewrittenMap[p.paragraphIdx] }}</text>
      </view>
    </view>
  </scroll-view>
</template>

<style lang="scss" scoped>
.page { padding: 24rpx; }

.processing {
  background: #fef3c7;
  border-radius: 20rpx;
  padding: 60rpx 40rpx;
  text-align: center;
}
.processing-icon { font-size: 80rpx; display: block; margin-bottom: 16rpx; }
.processing-text { font-size: 26rpx; color: #92400e; }

.summary {
  border-radius: 20rpx;
  padding: 48rpx 32rpx;
  text-align: center;
}
.summary-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #111827;
  margin-bottom: 16rpx;
}
.summary-verdict {
  display: block;
  margin-top: 12rpx;
  font-size: 26rpx;
  font-weight: 600;
}

/* --- 通用卡片 --- */
.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-top: 20rpx;
}
.card-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #374151;
  margin-bottom: 20rpx;
}

/* --- 溯源 --- */
.source-row { display: flex; align-items: center; margin-bottom: 16rpx; }
.source-label { width: 140rpx; font-size: 26rpx; color: #6b7280; }
.bar-track {
  flex: 1;
  height: 16rpx;
  background: #e5e7eb;
  border-radius: 8rpx;
  margin: 0 16rpx;
  overflow: hidden;
}
.bar-fill { height: 100%; transition: width 0.4s; }
.source-ratio { width: 80rpx; font-size: 24rpx; color: #374151; text-align: right; }

.legend {
  display: flex;
  gap: 24rpx;
  margin: 24rpx 8rpx 0;
  font-size: 22rpx;
  color: #6b7280;
}
.legend-item { display: inline-flex; align-items: center; }
.swatch {
  display: inline-block;
  width: 40rpx;
  height: 20rpx;
  margin-right: 8rpx;
  border-radius: 4rpx;
}
.high { background: #fee2e2; }
.mid  { background: #fef3c7; }

/* --- 段落 --- */
.para {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-top: 20rpx;
}
.para-header { display: flex; justify-content: space-between; margin-bottom: 16rpx; }
.para-idx { font-size: 22rpx; color: #9ca3af; }
.para-prob { font-size: 22rpx; font-weight: 600; }
.para-text { font-size: 28rpx; line-height: 1.7; color: #111827; }

.humanize-btn {
  margin-top: 24rpx;
  border: 1rpx solid #1a56db;
  background: #fff;
  color: #1a56db;
  font-size: 26rpx;
  font-weight: 600;
  border-radius: 12rpx;
}

/* --- 改写结果 --- */
.rewritten {
  margin-top: 24rpx;
  background: #eff6ff;
  border-radius: 12rpx;
  padding: 24rpx;
}
.rewritten-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}
.rewritten-label {
  font-size: 22rpx;
  color: #1a56db;
  font-weight: 600;
}
.rewritten-actions {
  display: flex;
  gap: 20rpx;
}
.rewritten-btn {
  font-size: 24rpx;
  color: #1a56db;
  padding: 4rpx 16rpx;
  border: 1rpx solid #1a56db;
  border-radius: 9999rpx;
  &.primary {
    background: #1a56db;
    color: #fff;
  }
}
.rewritten-text {
  font-size: 28rpx;
  line-height: 1.7;
  color: #1e3a8a;
}

/* --- diff 三色 --- */
.diff-text {
  font-size: 28rpx;
  line-height: 1.7;
}
.diff-equal  { color: #1e3a8a; }
.diff-add    { background: #d1fae5; color: #065f46; }
.diff-remove { background: #fee2e2; color: #991b1b; text-decoration: line-through; }
</style>
