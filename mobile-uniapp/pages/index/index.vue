<script setup>
import { ref } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { listTasks } from '@/api/detect'

const tasks = ref([])
const loading = ref(false)

const STATUS_MAP = {
  PENDING: { text: '排队中', color: '#9ca3af' },
  RUNNING: { text: '检测中', color: '#f59e0b' },
  DONE:    { text: '已完成', color: '#10b981' },
  FAILED:  { text: '失败',   color: '#ef4444' },
}
const DEGREE_MAP = { BACHELOR: '本科', MASTER: '硕士', PHD: '博士' }

async function load() {
  loading.value = true
  try {
    tasks.value = await listTasks()
  } catch (e) {
    // 错误已由 request.js 提示
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

onShow(load)
onPullDownRefresh(load)

function aiRateColor(rate, threshold) {
  if (rate <= threshold) return '#10b981'
  if (rate <= threshold * 1.5) return '#f59e0b'
  return '#ef4444'
}

function goDetail(id) {
  uni.navigateTo({ url: `/pages/task/detail?id=${id}` })
}
</script>

<template>
  <view class="list">
    <view
      v-for="t in tasks" :key="t.id"
      class="card" @click="goDetail(t.id)"
    >
      <view class="row">
        <text class="title">{{ t.paperTitle }}</text>
        <text class="status" :style="{ color: STATUS_MAP[t.status].color }">
          {{ STATUS_MAP[t.status].text }}
        </text>
      </view>
      <view class="row">
        <text class="meta">{{ DEGREE_MAP[t.degreeType] }} · 红线 {{ t.threshold }}% · {{ t.createdAt }}</text>
        <text
          v-if="t.status === 'DONE' && t.aiRate != null"
          class="rate" :style="{ color: aiRateColor(t.aiRate, t.threshold) }"
        >
          AI 率 {{ t.aiRate.toFixed(1) }}%
        </text>
      </view>
    </view>

    <view v-if="!loading && tasks.length === 0" class="empty">
      暂无检测记录，去「上传」提交论文
    </view>
  </view>
</template>

<style lang="scss" scoped>
.list {
  padding: 24rpx;
}

.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.04);
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;

  &:last-child { margin-top: 16rpx; }
}

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

.status { font-size: 24rpx; font-weight: 600; }

.meta { font-size: 22rpx; color: #6b7280; }

.rate { font-size: 32rpx; font-weight: 700; }

.empty {
  text-align: center;
  color: #9ca3af;
  padding-top: 200rpx;
  font-size: 26rpx;
}
</style>
