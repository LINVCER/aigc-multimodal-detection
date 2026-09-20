<script setup>
import { ref, computed } from 'vue'
import { onShow, onPullDownRefresh } from '@dcloudio/uni-app'
import { listMyFeedback } from '@/api/feedback'
import { useAuth } from '@/store/auth'

const auth = useAuth()

const list = ref([])
const loading = ref(false)

async function load() {
  if (!auth.userId) {
    list.value = []
    return
  }
  loading.value = true
  try { list.value = await listMyFeedback(auth.userId) }
  catch (e) {
    // request.js 已 toast，本页仅 DEV 日志
    // eslint-disable-next-line
    if (import.meta.env.DEV) {
      console.warn('[feedback/mine] load failed:', e?.message)
    }
  } finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

onShow(load)
onPullDownRefresh(load)

/* ---------- 语义映射 ---------- */
const CATEGORY = {
  bug:        { label: 'Bug',   tint: '#FF9500', wash: 'rgba(255,149,0,0.10)' },
  suggestion: { label: '建议',  tint: '#5856D6', wash: 'rgba(88,86,214,0.10)' },
  appeal:     { label: '结果申诉', tint: '#FF3B30', wash: 'rgba(255,59,48,0.10)' },
}
const STATUS = {
  PENDING:    { text: '待处理', color: '#B26200', bg: 'rgba(255,149,0,0.14)' },
  PROCESSING: { text: '处理中', color: '#0056B3', bg: 'rgba(0,122,255,0.14)' },
  REPLIED:    { text: '已回复', color: '#1B7F3E', bg: 'rgba(52,199,89,0.14)' },
  IGNORED:    { text: '已忽略', color: '#48484A', bg: 'rgba(142,142,147,0.14)' },
}
const categoryOf = (k) => CATEGORY[k] || { label: k, tint: '#8E8E93', wash: 'rgba(142,142,147,0.14)' }
const statusOf   = (k) => STATUS[k]   || STATUS.PENDING

/* ---------- 折叠 ---------- */
const expandedMap = ref({})
function toggleExpand(id) { expandedMap.value[id] = !expandedMap.value[id] }

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/profile/profile' })
}
function goTask(taskId) {
  if (!taskId) return
  uni.navigateTo({ url: `/pages/task/detail?id=${taskId}` })
}

const groupedByStatus = computed(() => {
  const pending = list.value.filter(f => f.status === 'PENDING' || f.status === 'PROCESSING')
  const handled = list.value.filter(f => f.status === 'REPLIED' || f.status === 'IGNORED')
  return { pending, handled }
})
</script>

<template>
  <view class="page">
    <view class="back-bar" hover-class="back-bar-hover" @click="goBack">
      <text class="back-arrow">‹</text>
      <text class="back-text">我的</text>
    </view>

    <view class="hero-header">
      <text class="large-title">我的反馈</text>
      <text class="hero-sub">已提交 {{ list.length }} 条 · 下拉刷新看回复</text>
    </view>

    <view v-if="!auth.userId" class="empty-card">
      <text class="empty-text">未登录 · 请先登录后查看反馈历史</text>
    </view>

    <view v-else-if="!loading && list.length === 0" class="empty-card">
      <text class="empty-text">还没有反馈记录</text>
      <text class="empty-sub">通过「我的 → 意见反馈」或「报告详情 → 结果申诉」提交</text>
    </view>

    <template v-else>
      <!-- 待处理 -->
      <template v-if="groupedByStatus.pending.length">
        <text class="section-label">待处理</text>
        <view class="list">
          <view
            v-for="f in groupedByStatus.pending" :key="f.id"
            class="card" hover-class="card-hover"
            @click="toggleExpand(f.id)"
          >
            <view class="card-head">
              <view class="cat-chip" :style="{ background: categoryOf(f.category).wash, color: categoryOf(f.category).tint }">
                {{ categoryOf(f.category).label }}
              </view>
              <view class="status-chip" :style="{ background: statusOf(f.status).bg, color: statusOf(f.status).color }">
                {{ statusOf(f.status).text }}
              </view>
            </view>
            <text class="card-content" :class="{ clamp: !expandedMap[f.id] }">{{ f.content }}</text>
            <view class="card-meta">
              <text>{{ f.createdAt }}</text>
              <text v-if="f.taskId" class="task-link" @click.stop="goTask(f.taskId)">查看任务 #{{ f.taskId }} ›</text>
            </view>
          </view>
        </view>
      </template>

      <!-- 已处理 -->
      <template v-if="groupedByStatus.handled.length">
        <text class="section-label">已处理</text>
        <view class="list">
          <view
            v-for="f in groupedByStatus.handled" :key="f.id"
            class="card" hover-class="card-hover"
            @click="toggleExpand(f.id)"
          >
            <view class="card-head">
              <view class="cat-chip" :style="{ background: categoryOf(f.category).wash, color: categoryOf(f.category).tint }">
                {{ categoryOf(f.category).label }}
              </view>
              <view class="status-chip" :style="{ background: statusOf(f.status).bg, color: statusOf(f.status).color }">
                {{ statusOf(f.status).text }}
              </view>
            </view>
            <text class="card-content" :class="{ clamp: !expandedMap[f.id] }">{{ f.content }}</text>

            <view v-if="expandedMap[f.id] && f.handledReply" class="reply-card">
              <text class="reply-label">运营回复 · {{ f.handledAt || '' }}</text>
              <text class="reply-text">{{ f.handledReply }}</text>
            </view>

            <view class="card-meta">
              <text>{{ f.createdAt }}</text>
              <text v-if="f.taskId" class="task-link" @click.stop="goTask(f.taskId)">查看任务 #{{ f.taskId }} ›</text>
            </view>
          </view>
        </view>
      </template>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

.back-bar {
  display: flex; align-items: center;
  height: 60rpx;
  padding: 0 $sp-1;
  margin-bottom: $sp-1;
  transition: opacity $duration-fast;
}
.back-bar-hover { opacity: 0.6; }
.back-arrow {
  font-size: 44rpx;
  color: $brand-primary;
  line-height: 1;
  margin-right: 4rpx;
}
.back-text {
  font-size: $fs-callout;
  color: $brand-primary;
  font-weight: $fw-medium;
}

.hero-header { padding: $sp-1 $sp-1 $sp-3; }
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

.section-label {
  display: block;
  padding: $sp-4 $sp-3 $sp-2;
  font-size: $fs-footnote;
  font-weight: $fw-medium;
  color: $label-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wide;
}
.list { display: flex; flex-direction: column; gap: $sp-2; }

.card {
  @include card;
  padding: $sp-3 $sp-4;
  transition: background $duration-fast;
}
.card-hover { background: rgba(60, 60, 67, 0.04); }
.card-head {
  display: flex; align-items: center; gap: $sp-2;
  margin-bottom: $sp-2;
}
.cat-chip, .status-chip {
  display: inline-flex; align-items: center;
  height: 40rpx;
  padding: 0 $sp-2;
  border-radius: $radius-pill;
  font-size: $fs-caption-1;
  font-weight: $fw-semibold;
}
.card-content {
  display: block;
  font-size: $fs-callout;
  color: $label-primary;
  line-height: $lh-normal;
  &.clamp {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
  }
}
.card-meta {
  margin-top: $sp-3;
  padding-top: $sp-2;
  border-top: $stroke-hairline solid $separator;
  display: flex; justify-content: space-between; align-items: center;
  font-size: $fs-caption-1;
  color: $label-secondary;
}
.task-link {
  color: $brand-primary;
  font-weight: $fw-medium;
}

.reply-card {
  margin-top: $sp-3;
  padding: $sp-3;
  background: $success-bg;
  border-radius: $radius-md;
}
.reply-label {
  display: block;
  font-size: $fs-caption-1;
  color: $success-fg;
  font-weight: $fw-semibold;
  margin-bottom: 6rpx;
}
.reply-text {
  display: block;
  font-size: $fs-subhead;
  color: $label-primary;
  line-height: $lh-normal;
}

.empty-card {
  @include card;
  margin-top: $sp-6;
  padding: 80rpx $sp-5;
  text-align: center;
}
.empty-text {
  display: block;
  font-size: $fs-headline;
  color: $label-primary;
  font-weight: $fw-medium;
}
.empty-sub {
  display: block;
  margin-top: $sp-2;
  font-size: $fs-subhead;
  color: $label-secondary;
  line-height: $lh-normal;
}
</style>
