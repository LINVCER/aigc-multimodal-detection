<script setup>
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { listTasks } from '@/api/detect'
import { DEGREE_MAP, STATUS_FILTER_OPTIONS, aiRateColor } from '@/utils/constants'
import StatusChip from '@/components/StatusChip.vue'
import EmptyState from '@/components/EmptyState.vue'
import Skeleton from '@/components/Skeleton.vue'

const tasks = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const statusFilter = ref('ALL')
let pollTimer = null

const filtered = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return tasks.value.filter((t) => {
    const kwHit = !kw || (t.paperTitle || '').toLowerCase().includes(kw)
    const stHit = statusFilter.value === 'ALL' || t.status === statusFilter.value
    return kwHit && stHit
  })
})

const hasRunning = computed(() =>
  tasks.value.some((t) => t.status === 'RUNNING' || t.status === 'PENDING'))

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    tasks.value = await listTasks()
  } catch (e) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

function ensurePolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (hasRunning.value) load(true)
    else stopPolling()
  }, 4000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

onShow(async () => {
  await load()
  if (hasRunning.value) ensurePolling()
  else stopPolling()
})
onPullDownRefresh(load)

function goDetail(id) { uni.navigateTo({ url: `/pages/task/detail?id=${id}` }) }
function goUpload() { uni.switchTab({ url: '/pages/upload/upload' }) }
</script>

<template>
  <view class="page">
    <!-- Large Title -->
    <view class="large-title-bar">
      <text class="large-title">检测记录</text>
    </view>

    <!-- 搜索栏（iOS 风磨砂）-->
    <view class="search-wrap">
      <view class="search">
        <text class="search-icon">􀊫</text>
        <input
          class="search-input"
          v-model="keyword"
          placeholder="搜索论文标题"
          placeholder-style="color: rgba(60,60,67,0.30)"
          confirm-type="search"
        />
        <text v-if="keyword" class="search-clear" @click="keyword = ''">✕</text>
      </view>

      <!-- 状态 segmented -->
      <scroll-view scroll-x class="chip-scroll" show-scrollbar="false">
        <view
          v-for="opt in STATUS_FILTER_OPTIONS" :key="opt.key"
          class="chip" :class="{ active: statusFilter === opt.key }"
          @click="statusFilter = opt.key"
        >{{ opt.text }}</view>
      </scroll-view>
    </view>

    <!-- 状态：loading / error / empty / list -->
    <Skeleton v-if="loading && tasks.length === 0" :rows="4" />

    <EmptyState
      v-else-if="error && tasks.length === 0"
      icon="⚠️" :title="error" desc="下拉可重试，或检查网络后重新进入"
      actionText="重新加载" @action="load()"
    />

    <EmptyState
      v-else-if="filtered.length === 0 && !keyword && statusFilter === 'ALL'"
      icon="📭" title="还没有检测记录"
      desc="上传你的论文，几十秒内拿到 AI 率报告"
      actionText="去上传" @action="goUpload"
    />

    <EmptyState
      v-else-if="filtered.length === 0"
      icon="🔎" title="没有匹配的记录"
      desc="试试其它关键词或筛选条件"
    />

    <!-- Inset Grouped List -->
    <view v-else class="list-group">
      <view class="group-card">
        <view
          v-for="(t, idx) in filtered" :key="t.id"
          class="row" hover-class="row-hover" @click="goDetail(t.id)"
        >
          <view class="row-main">
            <view class="row-title-line">
              <text class="row-title">{{ t.paperTitle }}</text>
              <StatusChip :status="t.status" />
            </view>
            <view class="row-meta">
              <text class="degree-tag">{{ DEGREE_MAP[t.degreeType]?.label || t.degreeType }}</text>
              <text class="meta-sep">·</text>
              <text>红线 {{ t.threshold }}%</text>
              <text class="meta-sep">·</text>
              <text>{{ t.createdAt }}</text>
            </view>
          </view>

          <view class="row-tail">
            <text
              v-if="t.status === 'DONE' && t.aiRate != null"
              class="rate"
              :style="{ color: aiRateColor(t.aiRate, t.threshold) }"
            >{{ t.aiRate.toFixed(1) }}%</text>
            <text class="chevron">›</text>
          </view>

          <!-- 分隔线：最后一个不显示 -->
          <view v-if="idx < filtered.length - 1" class="separator"></view>
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; padding-bottom: 40rpx; background: #F2F2F7; }

/* Large Title */
.large-title-bar {
  padding: 40rpx 40rpx 12rpx;
  background: #F2F2F7;
}
.large-title {
  font-size: 68rpx;
  font-weight: 700;
  letter-spacing: -1rpx;
  color: #000;
}

/* 搜索栏 */
.search-wrap {
  padding: 20rpx 32rpx 16rpx;
  background: #F2F2F7;
}
.search {
  display: flex;
  align-items: center;
  background: rgba(120,120,128,0.12);
  border-radius: 20rpx;
  padding: 0 24rpx;
  height: 72rpx;
}
.search-icon { font-size: 28rpx; margin-right: 12rpx; color: rgba(60,60,67,0.60); }
.search-input { flex: 1; font-size: 32rpx; height: 100%; color: #000; }
.search-clear { color: rgba(60,60,67,0.60); font-size: 28rpx; padding: 0 12rpx; }

.chip-scroll { white-space: nowrap; margin-top: 20rpx; }
.chip {
  display: inline-block;
  padding: 10rpx 28rpx;
  border-radius: 9999rpx;
  background: rgba(255,255,255,0.72);
  color: #000;
  font-size: 26rpx;
  font-weight: 500;
  margin-right: 16rpx;
  transition: background 200ms cubic-bezier(0.32, 0.72, 0, 1),
              color 200ms;
  &.active { background: #007AFF; color: #fff; font-weight: 600; }
}

/* Inset Grouped */
.list-group { padding: 24rpx 32rpx 0; }
.group-card {
  background: #FFFFFF;
  border-radius: 28rpx;
  overflow: hidden;
}
.row {
  padding: 32rpx 32rpx;
  display: flex;
  align-items: flex-start;
  transition: background-color 150ms;
  position: relative;
}
.row-hover { background: rgba(60,60,67,0.06); }

.row-main { flex: 1; min-width: 0; }
.row-title-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
  margin-bottom: 12rpx;
}
.row-title {
  flex: 1;
  font-size: 32rpx;
  font-weight: 600;
  color: #000;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  letter-spacing: -0.3rpx;
}
.row-meta {
  font-size: 24rpx;
  color: rgba(60,60,67,0.60);
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
}
.meta-sep { margin: 0 12rpx; opacity: 0.4; }
.degree-tag {
  background: rgba(0,122,255,0.10);
  color: #007AFF;
  padding: 4rpx 14rpx;
  border-radius: 8rpx;
  font-weight: 600;
  font-size: 22rpx;
}

.row-tail {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: space-between;
  padding-left: 20rpx;
  min-width: 100rpx;
}
.rate { font-size: 36rpx; font-weight: 700; letter-spacing: -0.5rpx; font-variant-numeric: tabular-nums; }
.chevron { color: rgba(60,60,67,0.30); font-size: 32rpx; margin-top: 8rpx; }

/* 组内分隔线：左侧留 padding 与 iOS Insets 一致 */
.separator {
  position: absolute;
  left: 32rpx; right: 0; bottom: 0;
  height: 1rpx;
  background: rgba(60,60,67,0.18);
}
</style>
