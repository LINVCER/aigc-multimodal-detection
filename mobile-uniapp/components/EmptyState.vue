<script setup>
defineProps({
  icon: { type: String, default: '📭' },
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' },
  actionText: { type: String, default: '' },
})
const emit = defineEmits(['action'])
</script>

<template>
  <view class="empty">
    <text class="icon">{{ icon }}</text>
    <text class="title">{{ title }}</text>
    <text v-if="desc" class="desc">{{ desc }}</text>
    <button v-if="actionText" class="action" @click="emit('action')">{{ actionText }}</button>
  </view>
</template>

<style lang="scss" scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 160rpx 60rpx 80rpx;
}
.icon { font-size: 120rpx; opacity: 0.6; margin-bottom: 32rpx; }
.title { font-size: 30rpx; color: #4b5563; font-weight: 600; }
.desc { font-size: 24rpx; color: #9ca3af; margin-top: 16rpx; text-align: center; line-height: 1.6; }
.action {
  margin-top: 48rpx;
  min-width: 300rpx;
  background: #1a56db;
  color: #fff;
  font-size: 28rpx;
  font-weight: 600;
  border-radius: 16rpx;
}
</style>
