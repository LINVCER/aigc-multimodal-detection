<template>
  <div class="gauge-container">
    <svg viewBox="0 0 120 70" class="gauge-svg">
      <path d="M 10 60 A 50 50 0 0 1 110 60" fill="none" stroke="#e2e8f0" stroke-width="12" />
      <path
        d="M 10 60 A 50 50 0 0 1 110 60"
        fill="none"
        :stroke="gaugeColor"
        stroke-width="12"
        stroke-linecap="round"
        :stroke-dasharray="dashArray"
        :stroke-dashoffset="0"
        style="transition: stroke-dasharray 0.5s ease"
      />
      <text x="60" y="55" text-anchor="middle" :fill="gaugeColor" font-size="18" font-weight="bold">
        {{ (value * 100).toFixed(0) }}%
      </text>
    </svg>
    <div class="gauge-label">{{ label }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue"

const props = defineProps<{
  value: number   // 0-1
  label?: string
}>()

const arcLength = Math.PI * 50  // 半圆弧长
const dashArray = computed(() => `${arcLength * props.value} ${arcLength * 2}`)

const gaugeColor = computed(() => {
  if (props.value < 0.25) return "#10b981"   // 绿色 — 很可能是真人
  if (props.value < 0.7) return "#f59e0b"    // 橙色 — 不确定
  return "#ef4444"                            // 红色 — 很可能是 AI
})
</script>

<style scoped>
.gauge-container { display: flex; flex-direction: column; align-items: center; }
.gauge-svg { width: 140px; height: 80px; }
.gauge-label { margin-top: 2px; font-size: 12px; color: #718096; }
</style>
