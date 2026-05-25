<template>
  <el-card class="result-card" :class="`risk-${riskLevel}`">
    <template #header>
      <div class="card-header">
        <span>{{ title }}</span>
        <el-tag :type="verdictTagType">{{ verdict }}</el-tag>
      </div>
    </template>
    <ConfidenceGauge :value="confidence" :label="'置信度'" />
    <div v-if="warning" style="margin-top:12px">
      <el-alert type="warning" :title="warning" show-icon :closable="false" />
    </div>
    <div v-if="modelAttr?.length" style="margin-top:12px">
      <div style="font-size:13px;color:#718096;margin-bottom:4px">模型溯源</div>
      <el-tag v-for="m in modelAttr" :key="m.model" size="small" style="margin:2px">
        {{ m.model }}: {{ (m.score * 100).toFixed(0) }}%
      </el-tag>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from "vue"
import ConfidenceGauge from "./ConfidenceGauge.vue"

const props = defineProps<{
  title: string
  verdict: string
  confidence: number
  riskLevel?: string
  warning?: string
  modelAttr?: { model: string; score: number }[]
}>()

const verdictTagType = computed(() => {
  if (props.verdict.includes("AI")) return "danger"
  if (props.verdict.includes("人类") || props.verdict.includes("真实")) return "success"
  return "warning"
})
</script>

<style scoped>
.result-card { text-align: center; }
.result-card.risk-high { border-left: 4px solid #ef4444; }
.result-card.risk-medium { border-left: 4px solid #f59e0b; }
.result-card.risk-low { border-left: 4px solid #10b981; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>
