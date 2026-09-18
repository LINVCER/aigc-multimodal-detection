<script setup>
import { computed } from 'vue'
import { STATUS_MAP } from '@/utils/constants'

const props = defineProps({
  status: { type: String, required: true },  // PENDING|RUNNING|DONE|FAILED
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
  padding: 4rpx 16rpx;
  border-radius: 9999rpx;
  font-size: 22rpx;
  font-weight: 600;
}
.dot {
  display: inline-block;
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: currentColor;
  margin-right: 8rpx;
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}
</style>
