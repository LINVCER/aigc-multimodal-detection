<script setup>
defineProps({
  rows: { type: Number, default: 3 },
})
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
.skeleton {
  padding: 24rpx;
}
.card {
  background: #fff;
  border-radius: 20rpx;
  padding: 28rpx;
  margin-bottom: 20rpx;
}
.line {
  height: 24rpx;
  border-radius: 12rpx;
  background: linear-gradient(90deg, #f3f4f6 0%, #e5e7eb 50%, #f3f4f6 100%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
}
.line-title { width: 70%; margin-bottom: 20rpx; }
.line-meta  { width: 40%; height: 20rpx; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
