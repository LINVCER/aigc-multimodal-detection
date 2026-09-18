<script setup>
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { listTasks } from '@/api/detect'
import { DEGREE_MAP, STATUS_FILTER_OPTIONS } from '@/utils/constants'
import AiRateBadge from '@/components/AiRateBadge.vue'
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

const hasRunning = computed(() => tasks.value.some((t) => t.status === 'RUNNING' || t.status === 'PENDING'))

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

/**
 * 存在进行中任务时，每 4s 静默刷新，避免用户手动下拉
 */
function ensurePolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => {
    if (hasRunning.value) load(true)
    else stopPolling()
  }, 4000)
}
function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

onShow(async () => {
  await load()
  if (hasRunning.value) ensurePolling()
  else stopPolling()
})
onPullDownRefresh(load)

function goDetail(id) {
  uni.navigateTo({ url: `/pages/task/detail?id=${id}` })
}
function goUpload() {
  uni.switchTab({ url: '/pages/upload/upload' })
}
</script>

<template>
  <view class="page">
    <!-- 搜索 + 状态筛选 -->
    <view class="filter-bar">
      <view class="search">
        <text class="search-icon">🔍</text>
        <input
          class="search-input"
          v-model="keyword"
          placeholder="搜索论文标题"
          confirm-type="search"
        />
        <text v-if="keyword" class="search-clear" @click="keyword = ''">✕</text>
      </view>
      <scroll-view scroll-x class="chip-scroll" show-scrollbar="false">
        <view
          v-for="opt in STATUS_FILTER_OPTIONS" :key="opt.key"
          class="chip" :class="{ active: statusFilter === opt.key }"
          @click="statusFilter = opt.key"
        >{{ opt.text }}</view>
      </scroll-view>
    </view>

    <!-- 加载中 -->
    <Skeleton v-if="loading && tasks.length === 0" :rows="4" />

    <!-- 加载失败 -->
    <EmptyState
      v-else-if="error && tasks.length === 0"
      icon="⚠️" :title="error" desc="下拉可重试，或检查网络后重新进入"
      actionText="重新加载" @action="load()"
    />

    <!-- 空 -->
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

    <!-- 列表 -->
    <view v-else class="list">
      <view
        v-for="t in filtered" :key="t.id"
        class="card" hover-class="card-hover" @click="goDetail(t.id)"
      >
        <view class="row row-title">
          <text class="title">{{ t.paperTitle }}</text>
          <StatusChip :status="t.status" />
        </view>
        <view class="row row-body">
          <view class="meta">
            <text class="degree">{{ DEGREE_MAP[t.degreeType]?.label || t.degreeType }}</text>
            <text class="dot-sep">·</text>
            <text>红线 {{ t.threshold }}%</text>
            <text class="dot-sep">·</text>
            <text>{{ t.createdAt }}</text>
          </view>
          <AiRateBadge
            v-if="t.status === 'DONE'"
            :rate="t.aiRate" :threshold="t.threshold" size="md"
          />
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; }

/* --- 筛选栏 --- */
.filter-bar {
  background: #fff;
  padding: 20rpx 24rpx 16rpx;
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1rpx solid #e5e7eb;
}
.search {
  display: flex;
  align-items: center;
  background: #f3f4f6;
  border-radius: 24rpx;
  padding: 0 20rpx;
  height: 68rpx;
}
.search-icon { font-size: 26rpx; margin-right: 12rpx; opacity: 0.6; }
.search-input { flex: 1; font-size: 26rpx; height: 100%; }
.search-clear {
  color: #9ca3af;
  font-size: 24rpx;
  padding: 0 12rpx;
}

.chip-scroll {
  white-space: nowrap;
  margin-top: 20rpx;
}
.chip {
  display: inline-block;
  padding: 8rpx 24rpx;
  border-radius: 9999rpx;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 24rpx;
  margin-right: 16rpx;
  &.active {
    background: #1a56db;
    color: #fff;
    font-weight: 600;
  }
}

/* --- 列表 --- */
.list { padding: 24rpx; }
.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(17, 24, 39, 0.04);
  transition: transform 0.15s;
}
.card-hover { transform: scale(0.98); background: #f9fafb; }

.row { display: flex; justify-content: space-between; align-items: center; }
.row-title { margin-bottom: 16rpx; }
.title {
  flex: 1;
  font-size: 30rpx;
  font-weight: 600;
  color: #111827;
  margin-right: 16rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta {
  font-size: 22rpx;
  color: #6b7280;
  display: inline-flex;
  align-items: center;
}
.dot-sep { margin: 0 12rpx; opacity: 0.4; }
.degree {
  background: #eff6ff;
  color: #1a56db;
  padding: 2rpx 12rpx;
  border-radius: 8rpx;
  font-weight: 600;
}
</style>
