<script setup>
import { computed } from 'vue'
import { aiRateColor } from '@/utils/constants'

const props = defineProps({
  rate: { type: Number, default: null },     // 0-100
  threshold: { type: Number, default: 20 },
  size: { type: String, default: 'md' },     // sm | md | lg
})

const color = computed(() => aiRateColor(props.rate, props.threshold))
const sizeClass = computed(() => `size-${props.size}`)
</script>

<template>
  <text v-if="rate == null" class="badge" :class="sizeClass" :style="{ color: '#9ca3af' }">—</text>
  <text v-else class="badge" :class="sizeClass" :style="{ color }">
    {{ rate.toFixed(1) }}%
  </text>
</template>

<style lang="scss" scoped>
.badge {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5rpx;
}
.size-sm { font-size: 26rpx; }
.size-md { font-size: 34rpx; }
.size-lg { font-size: 96rpx; }
</style>
