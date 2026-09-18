<script setup>
defineProps({
  icon:       { type: String, default: '📭' },
  title:      { type: String, default: '暂无数据' },
  desc:       { type: String, default: '' },
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
  padding: 200rpx 80rpx 80rpx;
}
.icon  { font-size: 128rpx; opacity: 0.35; margin-bottom: 40rpx; }
.title { font-size: 40rpx; font-weight: 600; color: #000; letter-spacing: -0.5rpx; }
.desc  {
  font-size: 30rpx; color: rgba(60,60,67,0.60);
  margin-top: 16rpx; text-align: center; line-height: 1.5;
}
.action {
  margin-top: 56rpx;
  min-width: 300rpx;
  height: 88rpx;
  line-height: 88rpx;
  background: #007AFF;
  color: #fff;
  font-size: 32rpx;
  font-weight: 600;
  border-radius: 9999rpx;
  transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1);
  &:active { transform: scale(0.96); }
}
</style>
