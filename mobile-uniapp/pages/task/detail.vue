<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { getTaskDetail, requestHumanize } from '@/api/detect'

const detail = ref(null)
const rewrittenMap = ref({})           // { paragraphIdx: rewrittenText }
const humanizingMap = ref({})          // { paragraphIdx: bool }

const SOURCE_LABEL = {
  human: '人类', gpt: 'GPT', claude: 'Claude', qwen: '通义千问',
  deepseek: 'DeepSeek', glm: '智谱GLM', kimi: 'Kimi', ernie: '文心', other: '其他',
}

onLoad(async (query) => {
  const id = Number(query.id)
  try {
    detail.value = await getTaskDetail(id)
  } catch (e) {
    uni.showToast({ title: '加载失败', icon: 'none' })
  }
})

const pass = computed(() => {
  const d = detail.value
  return d && d.aiRate != null && d.aiRate <= d.threshold
})

const sortedSources = computed(() => {
  if (!detail.value?.sourceLabels) return []
  return Object.entries(detail.value.sourceLabels)
    .sort((a, b) => b[1] - a[1])
    .map(([label, ratio]) => ({ label, ratio }))
})

/**
 * 句子级底色：>=0.7 高疑似 / >=0.4 中等 / 其它无色
 */
function sentenceStyle(prob) {
  if (prob >= 0.7) return 'background-color: #fee2e2;'
  if (prob >= 0.4) return 'background-color: #fef3c7;'
  return ''
}

function paragraphProbColor(prob) {
  if (prob >= 0.7) return '#ef4444'
  if (prob >= 0.4) return '#f59e0b'
  return '#10b981'
}

async function humanize(idx) {
  humanizingMap.value[idx] = true
  try {
    rewrittenMap.value[idx] = await requestHumanize(detail.value.id, idx)
  } catch (e) {
    uni.showToast({ title: e?.message || '改写失败', icon: 'none' })
  } finally {
    humanizingMap.value[idx] = false
  }
}
</script>

<template>
  <scroll-view scroll-y class="page" v-if="detail">
    <!-- 总览卡 -->
    <view class="summary" :style="{ background: pass ? '#ecfdf5' : '#fef2f2' }">
      <text class="summary-title">{{ detail.paperTitle }}</text>
      <text class="summary-rate" :style="{ color: pass ? '#10b981' : '#ef4444' }">
        {{ detail.aiRate?.toFixed(1) }}%
      </text>
      <text class="summary-verdict">
        {{ pass ? `低于红线 ${detail.threshold}%，达标 ✓` : `超过红线 ${detail.threshold}%，建议修改后重检` }}
      </text>
    </view>

    <!-- 溯源分布 -->
    <view class="source-card">
      <text class="section-title">疑似来源分布</text>
      <view v-for="s in sortedSources" :key="s.label" class="source-row">
        <text class="source-label">{{ SOURCE_LABEL[s.label] || s.label }}</text>
        <view class="bar-track">
          <view class="bar-fill" :style="{ width: (s.ratio * 100) + '%' }"></view>
        </view>
        <text class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</text>
      </view>
    </view>

    <!-- 图例 -->
    <view class="legend">
      <text class="legend-item"><text class="swatch high">　</text> 高疑似 AI</text>
      <text class="legend-item"><text class="swatch mid">　</text> 中等疑似</text>
      <text class="legend-item">无底色 = 判定人写</text>
    </view>

    <!-- 段落列表 -->
    <view v-for="p in detail.paragraphs" :key="p.paragraphIdx" class="para-card">
      <view class="para-header">
        <text class="para-idx">第 {{ p.paragraphIdx + 1 }} 段</text>
        <text class="para-prob" :style="{ color: paragraphProbColor(p.calibratedProb) }">
          AI 概率 {{ (p.calibratedProb * 100).toFixed(0) }}%
          <text v-if="p.sourceLabel && p.sourceLabel !== 'human'">
            · 疑似{{ SOURCE_LABEL[p.sourceLabel] || p.sourceLabel }}
          </text>
        </text>
      </view>

      <!-- 句子级高亮 -->
      <view class="para-text">
        <text
          v-for="s in p.sentences" :key="s.sentenceIdx"
          :style="sentenceStyle(s.aiProb)"
        >{{ s.text }}</text>
      </view>

      <!-- 高危段落 → 一键降 AIGC -->
      <button
        v-if="p.calibratedProb >= 0.7 && !rewrittenMap[p.paragraphIdx]"
        class="humanize-btn"
        :loading="humanizingMap[p.paragraphIdx]"
        @click="humanize(p.paragraphIdx)"
      >✨ 降 AIGC 改写建议</button>

      <view v-if="rewrittenMap[p.paragraphIdx]" class="rewritten">
        <text class="rewritten-label">改写建议（请人工核对语义后使用）</text>
        <text class="rewritten-text">{{ rewrittenMap[p.paragraphIdx] }}</text>
      </view>
    </view>
  </scroll-view>
</template>

<style lang="scss" scoped>
.page { padding: 24rpx; }

.summary {
  border-radius: 20rpx;
  padding: 40rpx;
  text-align: center;
}
.summary-title { display: block; font-size: 30rpx; font-weight: 600; color: #111827; }
.summary-rate  { display: block; font-size: 96rpx; font-weight: 800; margin: 12rpx 0; }
.summary-verdict { font-size: 26rpx; color: #374151; }

.source-card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-top: 20rpx;
}
.section-title { display: block; font-size: 28rpx; font-weight: 600; color: #374151; margin-bottom: 20rpx; }
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
.bar-fill { height: 100%; background: #1a56db; }
.source-ratio { width: 80rpx; font-size: 24rpx; color: #374151; text-align: right; }

.legend {
  display: flex;
  gap: 24rpx;
  margin: 24rpx 8rpx 12rpx;
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

.para-card {
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

.rewritten {
  margin-top: 24rpx;
  background: #eff6ff;
  border-radius: 12rpx;
  padding: 24rpx;
}
.rewritten-label {
  display: block;
  font-size: 22rpx;
  color: #1a56db;
  font-weight: 600;
  margin-bottom: 12rpx;
}
.rewritten-text {
  font-size: 28rpx;
  line-height: 1.7;
  color: #1e3a8a;
}
</style>
