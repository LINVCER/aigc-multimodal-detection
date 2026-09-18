<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTaskDetail, requestHumanize } from '@/api/detect'
import type { TaskDetail, ParagraphResult } from '@/api/types'

const props = defineProps<{ id: string }>()
const router = useRouter()

const detail = ref<TaskDetail | null>(null)
const loading = ref(true)
const rewrittenMap = ref<Record<number, string>>({})
const humanizingMap = ref<Record<number, boolean>>({})
let pollTimer: any = null

const SOURCE_LABEL: Record<string, string> = {
  human: '人类', gpt: 'GPT', claude: 'Claude', qwen: '通义千问',
  deepseek: 'DeepSeek', glm: '智谱GLM', kimi: 'Kimi', ernie: '文心', other: '其他',
}

async function load() {
  try {
    detail.value = await getTaskDetail(Number(props.id))
  } catch { /* toast 由拦截器给 */ } finally {
    loading.value = false
  }
}

function shouldPoll() {
  return detail.value && (detail.value.status === 'PENDING' || detail.value.status === 'RUNNING')
}
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => {
    await load()
    if (!shouldPoll()) stopPolling()
  }, 3000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

onMounted(async () => { await load(); if (shouldPoll()) startPolling() })
onUnmounted(stopPolling)

const pass = computed(() => {
  const d = detail.value
  return d && d.aiRate != null && d.aiRate <= d.threshold
})

const sortedSources = computed(() => {
  if (!detail.value?.sourceLabels) return []
  return Object.entries(detail.value.sourceLabels)
    .sort(([, a], [, b]) => b - a)
    .map(([label, ratio]) => ({ label, ratio }))
})

function sentenceBg(prob: number): string {
  if (prob >= 0.7) return '#fee2e2'
  if (prob >= 0.4) return '#fef3c7'
  return 'transparent'
}

function paragraphProbColor(prob: number): string {
  if (prob >= 0.7) return '#ef4444'
  if (prob >= 0.4) return '#f59e0b'
  return '#10b981'
}

async function humanize(p: ParagraphResult) {
  humanizingMap.value[p.paragraphIdx] = true
  try {
    const resp = await requestHumanize(Number(props.id), p.paragraphIdx)
    rewrittenMap.value[p.paragraphIdx] = resp.rewrittenText
  } finally {
    humanizingMap.value[p.paragraphIdx] = false
  }
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败，请手动选择')
  }
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="title">检测报告</span>
        <span></span>
      </div>
    </el-header>

    <el-main v-loading="loading" class="main">
      <template v-if="detail">
        <!-- 进行中占位 -->
        <el-alert
          v-if="detail.status === 'PENDING' || detail.status === 'RUNNING'"
          type="warning" show-icon :closable="false"
          title="检测中，页面将自动刷新（约 15-30 秒）"
          style="margin-bottom: 16px"
        />

        <!-- 总览卡 -->
        <el-card v-if="detail.status === 'DONE'" class="summary" :style="{ background: pass ? '#ecfdf5' : '#fef2f2' }">
          <div class="summary-title">{{ detail.paperTitle }}</div>
          <div class="summary-rate" :style="{ color: pass ? '#10b981' : '#ef4444' }">
            {{ detail.aiRate?.toFixed(1) }}%
          </div>
          <div class="summary-verdict">
            {{ pass ? `✓ 低于红线 ${detail.threshold}%，达标` : `⚠ 超过红线 ${detail.threshold}%，建议修改后重检` }}
          </div>
        </el-card>

        <!-- 溯源分布 -->
        <el-card v-if="detail.status === 'DONE'" style="margin-top: 16px">
          <template #header><span style="font-weight: 600">疑似来源分布</span></template>
          <div v-for="s in sortedSources" :key="s.label" class="source-row">
            <span class="source-label">{{ SOURCE_LABEL[s.label] || s.label }}</span>
            <el-progress
              :percentage="Math.round(s.ratio * 100)"
              :stroke-width="10" :show-text="false" style="flex: 1"
            />
            <span class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</span>
          </div>
        </el-card>

        <!-- 图例 -->
        <div v-if="detail.status === 'DONE'" class="legend">
          <span><span class="swatch high"></span> 高疑似 AI</span>
          <span><span class="swatch mid"></span> 中等疑似</span>
          <span>无底色 = 判定人写</span>
        </div>

        <!-- 段落列表 -->
        <el-card v-for="p in detail.paragraphs || []" :key="p.paragraphIdx" class="para">
          <div class="para-header">
            <span class="para-idx">第 {{ p.paragraphIdx + 1 }} 段</span>
            <span class="para-prob" :style="{ color: paragraphProbColor(p.calibratedProb) }">
              AI 概率 {{ (p.calibratedProb * 100).toFixed(0) }}%
              <template v-if="p.sourceLabel && p.sourceLabel !== 'human'">
                · 疑似 {{ SOURCE_LABEL[p.sourceLabel] || p.sourceLabel }}
              </template>
            </span>
          </div>
          <div class="para-text">
            <span
              v-for="s in p.sentences" :key="s.sentenceIdx"
              :style="{ background: sentenceBg(s.aiProb) }"
            >{{ s.text }}</span>
          </div>

          <el-button
            v-if="p.calibratedProb >= 0.7 && !rewrittenMap[p.paragraphIdx]"
            plain type="primary" size="small" style="margin-top: 12px"
            :loading="humanizingMap[p.paragraphIdx]"
            @click="humanize(p)"
          >✨ 降 AIGC 改写建议</el-button>

          <div v-if="rewrittenMap[p.paragraphIdx]" class="rewritten">
            <div class="rewritten-header">
              <span class="rewritten-label">改写建议（请人工核对语义后使用）</span>
              <el-button link type="primary" @click="copyText(rewrittenMap[p.paragraphIdx])">复制</el-button>
            </div>
            <div class="rewritten-text">{{ rewrittenMap[p.paragraphIdx] }}</div>
          </div>
        </el-card>
      </template>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header { background: #fff; border-bottom: 1px solid #e5e7eb; padding: 0; }
.header-inner { height: 60px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.title { font-size: 16px; font-weight: 600; }
.main { padding: 24px; max-width: 900px; margin: 0 auto; }

.summary { text-align: center; padding: 16px; }
.summary-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.summary-rate { font-size: 56px; font-weight: 800; letter-spacing: -1px; }
.summary-verdict { font-size: 14px; color: #374151; margin-top: 4px; }

.source-row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.source-label { width: 80px; color: #6b7280; font-size: 13px; }
.source-ratio { width: 44px; text-align: right; font-size: 12px; color: #374151; }

.legend {
  display: flex; gap: 20px; margin: 12px 4px 0;
  font-size: 12px; color: #6b7280;
}
.swatch { display: inline-block; width: 20px; height: 10px; margin-right: 4px; border-radius: 2px; vertical-align: middle; }
.swatch.high { background: #fee2e2; }
.swatch.mid  { background: #fef3c7; }

.para { margin-top: 16px; }
.para-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 10px;
}
.para-idx { font-size: 12px; color: #9ca3af; }
.para-prob { font-size: 12px; font-weight: 600; }
.para-text { font-size: 14px; line-height: 1.75; color: #111827; }

.rewritten {
  margin-top: 12px; background: #eff6ff; border-radius: 8px; padding: 12px;
}
.rewritten-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.rewritten-label { font-size: 12px; color: #1a56db; font-weight: 600; }
.rewritten-text { font-size: 14px; line-height: 1.75; color: #1e3a8a; }
</style>
