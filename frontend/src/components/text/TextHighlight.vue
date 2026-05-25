<template>
  <div class="text-highlight" v-if="segments.length > 0">
    <div class="highlight-legend">
      <span class="legend-item"><span class="dot high"></span> 高风险 (&ge;70%)</span>
      <span class="legend-item"><span class="dot medium"></span> 中风险 (40-70%)</span>
      <span class="legend-item"><span class="dot low"></span> 低风险 (&lt;40%)</span>
    </div>
    <div class="highlight-body">
      <template v-for="(seg, i) in segments" :key="i">
        <el-popover
          v-if="seg.score !== undefined"
          placement="top"
          :width="300"
          trigger="hover"
          :show-after="300"
        >
          <template #reference>
            <span :class="riskClass(seg.score)" class="seg">{{ seg.text }}</span>
          </template>
          <div class="popover-content">
            <div><strong>AI 概率:</strong> {{ (seg.score * 100).toFixed(1) }}%</div>
            <div v-if="seg.reasons && seg.reasons.length">
              <strong>原因:</strong>
              <ul>
                <li v-for="(r, j) in seg.reasons" :key="j">{{ r }}</li>
              </ul>
            </div>
          </div>
        </el-popover>
        <span v-else class="seg">{{ seg.text }}</span>
      </template>
    </div>
  </div>
  <div v-else class="text-plain">{{ text }}</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Segment {
  text: string
  score?: number
  reasons?: string[]
}

const props = defineProps<{
  text: string
  segments?: Segment[]
  threshold?: number
}>()

const segments = computed(() => {
  if (props.segments && props.segments.length > 0) return props.segments
  return []
})

function riskClass(score: number): string {
  if (score >= 0.7) return 'seg-high'
  if (score >= 0.4) return 'seg-medium'
  return 'seg-low'
}
</script>

<style scoped>
.text-highlight { margin-top: 12px; }
.highlight-legend { display: flex; gap: 16px; margin-bottom: 8px; font-size: 12px; }
.legend-item { display: flex; align-items: center; gap: 4px; }
.dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
.dot.high { background: var(--el-color-danger); }
.dot.medium { background: var(--el-color-warning); }
.dot.low { background: var(--el-color-success); }
.highlight-body { line-height: 1.9; padding: 12px; background: var(--el-fill-color-lighter); border-radius: 6px; white-space: pre-wrap; }
.seg { cursor: default; transition: background 0.15s; padding: 2px 1px; border-radius: 2px; }
.seg-high { background: rgba(245, 108, 108, 0.25); border-bottom: 2px solid var(--el-color-danger); }
.seg-medium { background: rgba(230, 162, 60, 0.2); border-bottom: 2px solid var(--el-color-warning); }
.seg-low { background: rgba(103, 194, 58, 0.12); }
.seg:hover { filter: brightness(0.9); }
.text-plain { white-space: pre-wrap; line-height: 1.9; padding: 12px; background: var(--el-fill-color-lighter); border-radius: 6px; }
.popover-content { font-size: 13px; line-height: 1.6; }
.popover-content ul { margin: 4px 0 0 16px; padding: 0; }
</style>
