<script setup>
import { useAuth } from '@/store/auth'

const auth = useAuth()

function logout() {
  uni.showModal({
    title: '提示',
    content: '确定退出登录？',
    success: (res) => {
      if (res.confirm) auth.logout()
    },
  })
}
</script>

<template>
  <view class="container">
    <view class="card">
      <text class="avatar">👤</text>
      <text class="name">{{ auth.username || '已登录用户' }}</text>
    </view>

    <view class="menu">
      <view class="item">额度余额（接入后端后展示）</view>
      <view class="item">历史报告下载</view>
      <view class="item">关于与隐私政策</view>
    </view>

    <button class="logout" @click="logout">退出登录</button>
  </view>
</template>

<style lang="scss" scoped>
.container { padding: 32rpx; }

.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 48rpx;
  text-align: center;
}
.avatar { font-size: 96rpx; }
.name { display: block; font-size: 32rpx; font-weight: 600; margin-top: 16rpx; color: #111827; }

.menu {
  background: #fff;
  border-radius: 20rpx;
  margin-top: 32rpx;
}
.item {
  font-size: 28rpx;
  color: #374151;
  padding: 32rpx 36rpx;
  border-bottom: 1rpx solid #e5e7eb;
  &:last-child { border-bottom: none; }
}

.logout {
  background: #fff;
  color: #ef4444;
  font-size: 28rpx;
  font-weight: 600;
  margin-top: 32rpx;
  border-radius: 20rpx;
}
</style>
