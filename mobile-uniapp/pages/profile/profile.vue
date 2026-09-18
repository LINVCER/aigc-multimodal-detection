<script setup>
import { useAuth } from '@/store/auth'

const auth = useAuth()

function logout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出吗？',
    confirmColor: '#FF3B30',
    cancelColor: '#007AFF',
    success: (res) => { if (res.confirm) auth.logout() },
  })
}
</script>

<template>
  <view class="page">
    <view class="large-title-bar">
      <text class="large-title">我的</text>
    </view>

    <!-- 用户卡 -->
    <view class="user-card">
      <view class="avatar">
        <text>{{ (auth.username || 'U')[0].toUpperCase() }}</text>
      </view>
      <view class="user-info">
        <text class="user-name">{{ auth.username || '已登录用户' }}</text>
        <text class="user-role">学生 · 教育部合规检测</text>
      </view>
    </view>

    <!-- 分组列表 1 -->
    <text class="group-label">账户</text>
    <view class="group-card">
      <view class="row">
        <text class="row-title">额度余额</text>
        <view class="row-value">
          <text class="value-text">接入后端后展示</text>
          <text class="chevron">›</text>
        </view>
      </view>
      <view class="separator"></view>
      <view class="row">
        <text class="row-title">历史报告</text>
        <text class="chevron">›</text>
      </view>
    </view>

    <!-- 分组列表 2 -->
    <text class="group-label">关于</text>
    <view class="group-card">
      <view class="row">
        <text class="row-title">隐私政策</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator"></view>
      <view class="row">
        <text class="row-title">版本</text>
        <text class="value-text">v0.1.0</text>
      </view>
    </view>

    <!-- 退出登录（危险按钮，独立分组卡） -->
    <view class="group-card danger-card" hover-class="row-hover" @click="logout">
      <text class="danger-text">退出登录</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; padding: 40rpx 32rpx 100rpx; background: #F2F2F7; }

.large-title-bar { padding-bottom: 32rpx; }
.large-title {
  font-size: 68rpx;
  font-weight: 700;
  letter-spacing: -1rpx;
  color: #000;
}

/* 用户卡：大 Avatar + 姓名 */
.user-card {
  background: #FFFFFF;
  border-radius: 28rpx;
  padding: 40rpx 32rpx;
  display: flex;
  align-items: center;
}
.avatar {
  width: 120rpx; height: 120rpx;
  border-radius: 9999rpx;
  background: linear-gradient(135deg, #007AFF 0%, #5AC8FA 100%);
  color: #fff;
  font-size: 52rpx;
  font-weight: 600;
  display: flex; align-items: center; justify-content: center;
  margin-right: 32rpx;
}
.user-info { flex: 1; }
.user-name { display: block; font-size: 40rpx; font-weight: 600; color: #000; letter-spacing: -0.5rpx; }
.user-role { display: block; font-size: 26rpx; color: rgba(60,60,67,0.60); margin-top: 8rpx; }

/* Inset Grouped Sections */
.group-label {
  display: block;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(60,60,67,0.60);
  text-transform: uppercase;
  letter-spacing: 1rpx;
  padding: 40rpx 20rpx 12rpx;
}
.group-card {
  background: #FFFFFF;
  border-radius: 28rpx;
  overflow: hidden;
  position: relative;
}
.row {
  padding: 32rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background 150ms;
}
.row-hover { background: rgba(60,60,67,0.06); }
.row-title { font-size: 32rpx; color: #000; }
.row-value { display: flex; align-items: center; }
.value-text { font-size: 30rpx; color: rgba(60,60,67,0.60); margin-right: 12rpx; }
.chevron   { color: rgba(60,60,67,0.30); font-size: 36rpx; }

.separator {
  height: 1rpx;
  background: rgba(60,60,67,0.18);
  margin-left: 32rpx;
}

/* 危险卡：单独一个按钮式卡片 */
.danger-card {
  margin-top: 48rpx;
  padding: 32rpx;
  text-align: center;
  transition: background 150ms;
}
.danger-text {
  font-size: 34rpx;
  color: #FF3B30;
  font-weight: 500;
}
</style>
