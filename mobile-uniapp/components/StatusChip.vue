<script setup>
import { computed } from 'vue'
import { STATUS_MAP } from '@/utils/constants'

const props = defineProps({
  status: { type: String, required: true },
})
const conf = computed(() => STATUS_MAP[props.status] || STATUS_MAP.PENDING)
</script>

<template>
  <text class="chip" :style="{ color: conf.color, background: conf.bg }">
    <text v-if="status === 'RUNNING'" class="dot"></text>
    {{ conf.text }}
  </text>
</template>

<style lang="scss" scoped>
.chip {
  display: inline-flex;
  align-items: center;
  padding: 6rpx 20rpx;
  border-radius: 9999rpx;
  font-size: 24rpx;
  font-weight: 600;
  letter-spacing: 0.5rpx;
}
.dot {
  display: inline-block;
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: currentColor;
  margin-right: 10rpx;
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.35; }
  50%      { opacity: 1; }
}
</style>
