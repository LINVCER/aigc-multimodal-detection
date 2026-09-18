<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTaskDetail, requestHumanize, downloadReportPdf } from '@/api/detect'
import Skeleton from '@/components/Skeleton.vue'
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
const SOURCE_COLOR: Record<string, string> = {
  human: 'var(--system-green)', gpt: 'var(--system-purple)', claude: 'var(--system-pink)',
  qwen: 'var(--system-orange)', deepseek: 'var(--system-blue)', glm: 'var(--system-teal)',
  kimi: 'var(--system-purple)', ernie: 'var(--system-red)', other: 'var(--system-gray)',
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
  pollTimer = setInterval(async () => { await load(); if (!shouldPoll()) stopPolling() }, 3000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
onMounted(async () => { await load(); if (shouldPoll()) startPolling() })
onUnmounted(stopPolling)

const pass = computed(() => {
  const d = detail.value
  return d && d.aiRate != null && d.aiRate <= d.threshold
})
const summaryColor = computed(() => {
  const d = detail.value
  if (!d || d.aiRate == null) return 'var(--label-tertiary)'
  if (d.aiRate <= d.threshold) return 'var(--system-green)'
  if (d.aiRate <= d.threshold * 1.5) return 'var(--system-orange)'
  return 'var(--system-red)'
})
const sortedSources = computed(() => {
  if (!detail.value?.sourceLabels) return []
  return Object.entries(detail.value.sourceLabels).sort(([, a], [, b]) => b - a).map(([label, ratio]) => ({ label, ratio }))
})

function sentenceBg(prob: number): string {
  if (prob >= 0.7) return 'rgba(255, 59, 48, 0.14)'
  if (prob >= 0.4) return 'rgba(255, 149, 0, 0.16)'
  return 'transparent'
}
function paragraphProbColor(prob: number): string {
  if (prob >= 0.7) return 'var(--system-red)'
  if (prob >= 0.4) return 'var(--system-orange)'
  return 'var(--system-green)'
}

async function humanize(p: ParagraphResult) {
  humanizingMap.value[p.paragraphIdx] = true
  try {
    const resp = await requestHumanize(Number(props.id), p.paragraphIdx)
    rewrittenMap.value[p.paragraphIdx] = resp.rewrittenText
  } finally { humanizingMap.value[p.paragraphIdx] = false }
}

async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('已复制') }
  catch { ElMessage.warning('复制失败') }
}

const downloading = ref(false)
async function onDownloadPdf() {
  if (!detail.value) return
  downloading.value = true
  try {
    await downloadReportPdf(Number(props.id), detail.value.paperTitle)
    ElMessage.success('报告已下载')
  } catch (e: any) {
    ElMessage.error(e?.message || '下载失败')
  } finally { downloading.value = false }
}

const EXCLUDE_REASON_LABEL: Record<string, string> = {
  reference: '参考文献',
  acknowledgement: '致谢',
  appendix: '附录',
  sectionTitle: '章节标题',
  caption: '图表标题',
}

// 底部副标题：X 段正文 · 已排除 Y 段（参考文献/图表/…）
const bodyStats = computed(() => {
  if (!detail.value?.paragraphs) return null
  const body = detail.value.paragraphs.filter(p => !p.excluded).length
  const excluded = detail.value.paragraphs.length - body
  return { body, excluded }
})
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="header-title">检测报告</span>
        <el-button
          v-if="detail && detail.status === 'DONE'"
          type="primary" round size="small"
          :loading="downloading" @click="onDownloadPdf"
        >⬇  下载 PDF</el-button>
        <span v-else></span>
      </div>
    </el-header>

    <el-main class="main">
      <Skeleton v-if="loading" :rows="4" />

      <template v-else-if="detail">
        <div class="wrap">
          <!-- Processing -->
          <el-alert
            v-if="detail.status === 'PENDING' || detail.status === 'RUNNING'"
            type="warning" show-icon :closable="false"
            title="检测中，页面将自动刷新（约 15-30 秒）"
            style="margin-bottom: 20px"
          />

          <!-- Hero 大数字（Fitness 风） -->
          <el-card v-if="detail.status === 'DONE'" class="hero" body-style="padding: 40px 32px">
            <div class="hero-inner">
              <div class="hero-label">整体 AI 率</div>
              <div class="hero-rate-line">
                <span class="hero-rate" :style="{ color: summaryColor }">{{ detail.aiRate?.toFixed(1) }}</span>
                <span class="hero-unit">%</span>
              </div>
              <div class="hero-verdict" :style="{ color: summaryColor }">
                {{ pass ? '低于红线 ' + detail.threshold + '%，达标' : '超过红线 ' + detail.threshold + '%，建议修改后重检' }}
              </div>
              <div v-if="bodyStats" class="hero-body-hint">
                基于正文 {{ bodyStats.body }} 段计算<template v-if="bodyStats.excluded > 0">，已自动排除 {{ bodyStats.excluded }} 段（参考文献 / 图表标题 等）</template>
              </div>
              <div class="hero-paper">{{ detail.paperTitle }}</div>
            </div>
          </el-card>

          <!-- Sources -->
          <template v-if="detail.status === 'DONE'">
            <div class="section-header">疑似来源分布</div>
            <el-card class="section-card" body-style="padding: 8px 0">
              <div
                v-for="(s, i) in sortedSources" :key="s.label"
                class="source-item" :class="{ 'has-sep': i < sortedSources.length - 1 }"
              >
                <div class="source-line">
                  <span class="source-name-wrap">
                    <span class="source-dot" :style="{ background: SOURCE_COLOR[s.label] || 'var(--system-gray)' }"></span>
                    <span class="source-name">{{ SOURCE_LABEL[s.label] || s.label }}</span>
                  </span>
                  <span class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</span>
                </div>
                <el-progress
                  :percentage="Math.round(s.ratio * 100)"
                  :stroke-width="8"
                  :show-text="false"
                  :color="SOURCE_COLOR[s.label] || 'var(--system-gray)'"
                />
              </div>
            </el-card>
          </template>

          <!-- Paragraphs -->
          <template v-if="detail.status === 'DONE'">
            <div class="section-header-line">
              <div class="section-header">段落分析</div>
              <div class="legend">
                <span><span class="swatch high"></span> 高</span>
                <span><span class="swatch mid"></span> 中</span>
              </div>
            </div>

            <el-card
              v-for="p in detail.paragraphs || []" :key="p.paragraphIdx"
              class="para" :class="{ 'para-excluded': p.excluded }"
            >
              <div class="para-header">
                <span class="para-idx">段 {{ p.paragraphIdx + 1 }}</span>
                <span v-if="p.excluded" class="excluded-badge">
                  未参与计算 · {{ EXCLUDE_REASON_LABEL[p.excludeReason || ''] || '非正文' }}
                </span>
                <span
                  v-else
                  class="para-prob"
                  :style="{ color: paragraphProbColor(p.calibratedProb || 0) }"
                >
                  {{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%
                  <template v-if="p.sourceLabel && p.sourceLabel !== 'human'">
                    · 疑似 {{ SOURCE_LABEL[p.sourceLabel] || p.sourceLabel }}
                  </template>
                </span>
              </div>
              <div v-if="p.excluded" class="para-excluded-text">{{ p.text }}</div>
              <div v-else class="para-text">
                <span
                  v-for="s in p.sentences" :key="s.sentenceIdx"
                  :style="{ background: sentenceBg(s.aiProb) }"
                >{{ s.text }}</span>
              </div>

              <el-button
                v-if="!p.excluded && (p.calibratedProb || 0) >= 0.7 && !rewrittenMap[p.paragraphIdx]"
                type="primary" plain size="default" style="margin-top: 14px"
                :loading="humanizingMap[p.paragraphIdx]" @click="humanize(p)"
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
        </div>
      </template>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--label-quaternary);
  padding: 0; position: sticky; top: 0; z-index: 10;
}
.header-inner { height: 56px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.header-title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }

.main { padding: 32px 24px 48px; }
.wrap { max-width: 900px; margin: 0 auto; }

/* Hero */
.hero-inner { text-align: center; }
.hero-label {
  font-size: var(--fs-caption-1);
  font-weight: var(--fw-medium);
  color: var(--label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.hero-rate-line { display: inline-flex; align-items: baseline; margin: 16px 0 12px; }
.hero-rate {
  font-size: 88px;
  font-weight: var(--fw-bold);
  letter-spacing: -3px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.hero-unit { font-size: 32px; font-weight: var(--fw-semibold); color: var(--label-secondary); margin-left: 6px; }
.hero-verdict { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }
.hero-body-hint {
  font-size: var(--fs-footnote);
  color: var(--label-secondary);
  margin-top: 12px;
}
.hero-paper {
  font-size: var(--fs-subhead); color: var(--label-secondary);
  margin-top: 20px; padding-top: 20px;
  border-top: 1px solid var(--label-quaternary);
}

/* Section headers */
.section-header {
  font-size: var(--fs-caption-1);
  font-weight: var(--fw-medium);
  color: var(--label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 28px 12px 8px;
}
.section-header-line {
  display: flex; justify-content: space-between; align-items: baseline;
  padding-right: 12px;
}
.legend {
  font-size: var(--fs-caption-1); color: var(--label-secondary);
  display: inline-flex; gap: 16px;
}
.swatch { display: inline-block; width: 20px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
.swatch.high { background: rgba(255, 59, 48, 0.30); }
.swatch.mid  { background: rgba(255, 149, 0, 0.30); }

.section-card { }
.source-item { padding: 14px 20px; position: relative; }
.source-item.has-sep::after {
  content: ''; position: absolute; left: 20px; right: 0; bottom: 0; height: 1px;
  background: var(--label-quaternary);
}
.source-line { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.source-name-wrap { display: inline-flex; align-items: center; }
.source-dot { width: 10px; height: 10px; border-radius: 50%; margin-right: 10px; }
.source-name { font-size: var(--fs-body); color: var(--label); font-weight: var(--fw-medium); }
.source-ratio { font-size: 15px; color: var(--label); font-weight: var(--fw-semibold); font-variant-numeric: tabular-nums; }

/* Paragraphs */
.para { margin-top: 12px; }
.para-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.para-idx {
  font-size: 11px; font-weight: var(--fw-semibold);
  color: var(--label-secondary); letter-spacing: 0.8px; text-transform: uppercase;
}
.para-prob { font-size: var(--fs-footnote); font-weight: var(--fw-semibold); }
.para-text { font-size: 15px; line-height: 1.7; color: var(--label); }

/* 非正文段：整卡去饱和，徽章灰 */
.para-excluded { opacity: 0.7; }
.excluded-badge {
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
  background: rgba(120, 120, 128, 0.14);
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  font-weight: var(--fw-medium);
}
.para-excluded-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--label-secondary);
  font-style: normal;
}

.rewritten {
  margin-top: 14px;
  background: rgba(0, 122, 255, 0.06);
  border-radius: var(--radius-btn);
  padding: 14px 16px;
}
.rewritten-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rewritten-label { font-size: var(--fs-caption-1); color: var(--system-blue); font-weight: var(--fw-semibold); letter-spacing: 0.3px; }
.rewritten-text { font-size: 15px; line-height: 1.7; color: var(--label); }
</style>
