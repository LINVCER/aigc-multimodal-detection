<script setup>
defineProps({ rows: { type: Number, default: 3 } })
</script>

<template>
  <view class="skeleton">
    <view v-for="i in rows" :key="i" class="card">
      <view class="line line-title"></view>
      <view class="line line-meta"></view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.skeleton { padding: 24rpx 32rpx; }
.card {
  background: #fff;
  border-radius: 28rpx;
  padding: 40rpx;
  margin-bottom: 24rpx;
}
.line {
  height: 28rpx;
  border-radius: 14rpx;
  background: linear-gradient(90deg,
    rgba(60,60,67,0.06) 0%,
    rgba(60,60,67,0.14) 50%,
    rgba(60,60,67,0.06) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.6s cubic-bezier(0.32, 0.72, 0, 1) infinite;
}
.line-title { width: 70%; margin-bottom: 24rpx; }
.line-meta  { width: 40%; height: 24rpx; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
