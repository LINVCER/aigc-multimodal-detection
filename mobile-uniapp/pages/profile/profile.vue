<script setup>
import { ref, computed } from 'vue'
import { useAuth } from '@/store/auth'
import FeedbackSheet from '@/components/FeedbackSheet.vue'

const auth = useAuth()
const feedbackOpen = ref(false)

const avatarLetter = computed(() => (auth.username || 'U')[0].toUpperCase())
const roleText = computed(() =>
  auth.role === 'OPS_ADMIN' ? '运营团队 · 内部账号'
    : auth.role === 'ADMIN' ? '系统管理员'
    : '个人版 · AI 检测'
)

// manifest.json 里 versionName；uni.getSystemInfoSync().appVersion 在 H5 拿不到
// 简单硬编码，Wave 4 · Batch 4.4 引 .env.example 时同步暴露 VITE_APP_VERSION
const appVersion = '0.2.0'

function logout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出吗？',
    confirmColor: '#FF3B30',
    cancelColor: '#007AFF',
    success: (res) => { if (res.confirm) auth.logout() },
  })
}

function comingSoon(name) {
  uni.showToast({ title: `${name} 即将上线`, icon: 'none' })
}
</script>

<template>
  <view class="page">
    <!-- Large Title -->
    <view class="hero-header">
      <text class="large-title">我的</text>
    </view>

    <!-- 用户卡 -->
    <view class="user-card">
      <view class="avatar">
        <text>{{ avatarLetter }}</text>
      </view>
      <view class="user-info">
        <text class="user-name">{{ auth.username || '已登录用户' }}</text>
        <text class="user-role">{{ roleText }}</text>
      </view>
    </view>

    <!-- 账户 -->
    <text class="group-label">账户</text>
    <view class="group-card">
      <view class="row" hover-class="row-hover" @click="comingSoon('额度余额')">
        <text class="row-title">额度余额</text>
        <view class="row-tail">
          <text class="row-value muted">接入后展示</text>
          <text class="chevron">›</text>
        </view>
      </view>
      <view class="separator" />
      <view class="row" hover-class="row-hover" @click="comingSoon('历史报告')">
        <text class="row-title">历史报告</text>
        <text class="chevron">›</text>
      </view>
    </view>

    <!-- 反馈 -->
    <text class="group-label">反馈</text>
    <view class="group-card">
      <view class="row" hover-class="row-hover" @click="feedbackOpen = true">
        <text class="row-title">意见反馈</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator" />
      <view class="row" hover-class="row-hover" @click="comingSoon('我的反馈')">
        <text class="row-title">我的反馈</text>
        <view class="row-tail">
          <text class="row-value muted">查看回复</text>
          <text class="chevron">›</text>
        </view>
      </view>
    </view>

    <!-- 关于 -->
    <text class="group-label">关于</text>
    <view class="group-card">
      <view class="row" hover-class="row-hover" @click="comingSoon('隐私政策')">
        <text class="row-title">隐私政策</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator" />
      <view class="row">
        <text class="row-title">版本</text>
        <text class="row-value muted">v{{ appVersion }}</text>
      </view>
    </view>

    <!-- 退出登录 -->
    <view class="danger-card" hover-class="danger-card-hover" @click="logout">
      <text class="danger-text">退出登录</text>
    </view>

    <FeedbackSheet v-model="feedbackOpen" default-category="suggestion" />
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

/* Large Title */
.hero-header { padding: $sp-3 $sp-1 $sp-3; }
.large-title {
  display: block;
  font-size: $fs-large-title;
  font-weight: $fw-bold;
  line-height: $lh-tight;
  letter-spacing: $tracking-tight;
  color: $label-primary;
}

/* 用户卡 · gradient avatar + 姓名 */
.user-card {
  @include card;
  padding: $sp-5 $sp-4;
  display: flex;
  align-items: center;
}
.avatar {
  width: $size-avatar-lg; height: $size-avatar-lg;
  border-radius: $radius-pill;
  background: $brand-gradient;
  color: #FFFFFF;
  font-size: 52rpx;
  font-weight: $fw-semibold;
  display: flex; align-items: center; justify-content: center;
  margin-right: $sp-4;
  flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name {
  display: block;
  font-size: $fs-title-3;
  font-weight: $fw-semibold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
}
.user-role {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-top: 8rpx;
}

/* Inset Grouped Section */
.group-label {
  @include group-label;
}
.group-card {
  @include card-flush;
}

/* Row（Inset Grouped 单行） */
.row {
  min-height: $size-row-h;
  padding: $sp-3 $sp-4;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background $duration-fast $ease-standard;
}
.row-hover { background: rgba(60, 60, 67, 0.06); }
.row-title {
  font-size: $fs-body;
  color: $label-primary;
}
.row-tail {
  display: flex; align-items: center;
}
.row-value {
  font-size: $fs-subhead;
  color: $label-primary;
  margin-right: $sp-1;
  &.muted { color: $label-secondary; }
}
.chevron {
  color: $label-tertiary;
  font-size: $icon-md;
  line-height: 1;
  margin-left: $sp-1;
}
.separator {
  height: $stroke-hairline;
  background: $separator;
  margin-left: $sp-4;
}

/* 危险卡 · 单独按钮式卡片 */
.danger-card {
  @include card-flush;
  margin-top: $sp-6;
  padding: $sp-4;
  text-align: center;
  transition: background $duration-fast $ease-standard;
}
.danger-card-hover { background: rgba(60, 60, 67, 0.06); }
.danger-text {
  font-size: $fs-headline;
  color: $danger-solid;
  font-weight: $fw-medium;
}
</style>
