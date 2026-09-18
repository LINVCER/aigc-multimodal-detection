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

/**
 * 环形进度（SVG r=86 → 周长 ≈ 540.354）
 * AI 率 0-100% 映射为整圈；stroke-dashoffset = 周长 * (1 - rate/100)
 * 红线刻度定位在圈上 (threshold / 100) 的位置，作为一小段高亮
 */
const ringCircumference = 2 * Math.PI * 86  // ≈ 540.354
const ringOffset = computed(() => {
  const d = detail.value
  if (!d || d.aiRate == null) return ringCircumference
  const pct = Math.min(100, Math.max(0, d.aiRate)) / 100
  return ringCircumference * (1 - pct)
})
const ringThresholdOffset = computed(() => {
  const d = detail.value
  if (!d || d.threshold == null) return ringCircumference
  const pct = Math.min(100, Math.max(0, d.threshold)) / 100
  return ringCircumference * (1 - pct)
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

/**
 * 改进建议（Wave 1 · 2.4）：纯前端规则驱动，不需要后端返回
 * 依据整体 AI 率、章节高危段落、溯源分布给出可执行建议
 */
const suggestions = computed<Array<{ icon: string; title: string; body: string; severity: 'info' | 'warn' | 'danger' }>>(() => {
  const d = detail.value
  if (!d || d.status !== 'DONE' || d.aiRate == null) return []
  const out: Array<{ icon: string; title: string; body: string; severity: 'info' | 'warn' | 'danger' }> = []

  // 规则 1：整体 AI 率超线
  if (d.aiRate > d.threshold) {
    const gap = (d.aiRate - d.threshold).toFixed(1)
    out.push({
      icon: '📉',
      title: `AI 率超线 ${gap} 个百分点`,
      body: `你的 AI 率 ${d.aiRate.toFixed(1)}% 超过 ${d.threshold}% 红线。建议重点修改下方标红段落 —— 用自己的话重写核心观点，避免大段直接使用 AI 输出。`,
      severity: 'danger',
    })
  } else if (d.aiRate > d.threshold * 0.7) {
    out.push({
      icon: '⚠️',
      title: '接近红线，仍有修改空间',
      body: `AI 率 ${d.aiRate.toFixed(1)}%，距红线 ${d.threshold}% 已不足 ${(d.threshold - d.aiRate).toFixed(1)} 个百分点。建议对标黄段落做小幅改写，留出安全缓冲。`,
      severity: 'warn',
    })
  } else {
    out.push({
      icon: '✓',
      title: '整体达标',
      body: `AI 率 ${d.aiRate.toFixed(1)}%，明显低于 ${d.threshold}% 红线。继续保持原创性写作。`,
      severity: 'info',
    })
  }

  // 规则 2：高危段落集中定位
  const highRisk = (d.paragraphs || []).filter(p => !p.excluded && (p.calibratedProb || 0) >= 0.7)
  if (highRisk.length > 0) {
    const idxList = highRisk.slice(0, 5).map(p => '段' + (p.paragraphIdx + 1)).join('、')
    out.push({
      icon: '🎯',
      title: `${highRisk.length} 段高疑似 AI，优先处理`,
      body: `${idxList}${highRisk.length > 5 ? ' 等' : ''}被判为高疑似（≥70%）。点击右侧"降 AIGC 改写建议"可一键生成改写方案，人工核对语义后替换即可。`,
      severity: 'warn',
    })
  }

  // 规则 3：溯源占比集中
  if (d.sourceLabels) {
    const entries = Object.entries(d.sourceLabels)
      .filter(([k]) => k !== 'human')
      .sort((a, b) => b[1] - a[1])
    if (entries.length && entries[0][1] >= 0.4) {
      const src = SOURCE_LABEL[entries[0][0]] || entries[0][0]
      out.push({
        icon: '🔎',
        title: `疑似大量使用 ${src}`,
        body: `${(entries[0][1] * 100).toFixed(0)}% 段落被判为 ${src} 风格。建议避免连续段落使用同一 AI 助手，可在改写时切换措辞、调整句式节奏。`,
        severity: 'info',
      })
    }
  }

  // 规则 4：排除段占比过高（可能是格式问题）
  if (bodyStats.value && bodyStats.value.excluded > bodyStats.value.body) {
    out.push({
      icon: '📄',
      title: '识别到大量非正文段落',
      body: `${bodyStats.value.excluded} 段被识别为参考文献 / 图表 / 章节标题（未参与 AI 率计算）。如果这不符合预期，请确认论文正文是否使用了标准段落格式。`,
      severity: 'info',
    })
  }

  return out
})

function suggestionColor(sev: 'info' | 'warn' | 'danger'): string {
  return sev === 'danger' ? 'var(--system-red)' : sev === 'warn' ? 'var(--system-orange)' : 'var(--system-blue)'
}
function suggestionBg(sev: 'info' | 'warn' | 'danger'): string {
  return sev === 'danger' ? 'rgba(255, 59, 48, 0.08)'
    : sev === 'warn' ? 'rgba(255, 149, 0, 0.08)'
    : 'rgba(0, 122, 255, 0.06)'
}
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

          <!-- Hero 环形进度（Apple Fitness / Health 风）-->
          <el-card v-if="detail.status === 'DONE'" class="hero" body-style="padding: 40px 32px">
            <div class="hero-inner">
              <div class="hero-label">整体 AI 率</div>

              <!-- Circular progress ring：SVG stroke-dasharray 动画 -->
              <div class="ring-wrap">
                <svg class="ring" viewBox="0 0 200 200">
                  <!-- 背景圈 -->
                  <circle
                    cx="100" cy="100" r="86"
                    fill="none"
                    stroke="rgba(120, 120, 128, 0.16)"
                    stroke-width="14"
                  />
                  <!-- AI 率进度（顶端起，顺时针）-->
                  <circle
                    cx="100" cy="100" r="86"
                    fill="none"
                    :stroke="summaryColor"
                    stroke-width="14"
                    stroke-linecap="round"
                    :stroke-dasharray="ringCircumference"
                    :stroke-dashoffset="ringOffset"
                    transform="rotate(-90 100 100)"
                    style="transition: stroke-dashoffset 900ms cubic-bezier(0.32, 0.72, 0, 1)"
                  />
                  <!-- 红线刻度：一小段亮点标示阈值位置 -->
                  <circle
                    cx="100" cy="100" r="86"
                    fill="none"
                    :stroke="pass ? 'var(--system-green)' : 'var(--system-red)'"
                    stroke-width="14"
                    stroke-linecap="butt"
                    :stroke-dasharray="`3 ${ringCircumference - 3}`"
                    :stroke-dashoffset="ringThresholdOffset"
                    transform="rotate(-90 100 100)"
                    opacity="0.9"
                  />
                </svg>
                <div class="ring-center">
                  <div class="ring-rate" :style="{ color: summaryColor }">
                    {{ detail.aiRate?.toFixed(1) }}<span class="ring-unit">%</span>
                  </div>
                  <div class="ring-cap">红线 {{ detail.threshold }}%</div>
                </div>
              </div>

              <div class="hero-verdict" :style="{ color: summaryColor }">
                {{ pass ? '✓ 低于红线，达标' : '⚠ 超过红线 ' + detail.threshold + '%，建议修改后重检' }}
              </div>
              <div v-if="bodyStats" class="hero-body-hint">
                基于正文 {{ bodyStats.body }} 段计算<template v-if="bodyStats.excluded > 0">，已自动排除 {{ bodyStats.excluded }} 段（参考文献 / 图表标题 等）</template>
              </div>
              <div class="hero-paper">{{ detail.paperTitle }}</div>
            </div>
          </el-card>

          <!-- 改进建议（Wave 1 · 2.4） -->
          <template v-if="suggestions.length">
            <div class="section-header">改进建议</div>
            <el-card class="suggestion-card" body-style="padding: 0">
              <div
                v-for="(s, i) in suggestions" :key="i"
                class="suggestion-item"
                :class="{ 'has-sep': i < suggestions.length - 1 }"
                :style="{ background: suggestionBg(s.severity) }"
              >
                <div class="suggestion-icon" :style="{ color: suggestionColor(s.severity) }">{{ s.icon }}</div>
                <div class="suggestion-body">
                  <div class="suggestion-title" :style="{ color: suggestionColor(s.severity) }">{{ s.title }}</div>
                  <div class="suggestion-text">{{ s.body }}</div>
                </div>
              </div>
            </el-card>
          </template>

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

/* ---- 环形进度 ---- */
.ring-wrap {
  position: relative;
  width: 220px;
  height: 220px;
  margin: 20px auto 20px;
}
.ring {
  width: 100%;
  height: 100%;
  display: block;
}
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ring-rate {
  font-size: 56px;
  font-weight: var(--fw-bold);
  letter-spacing: -1.5px;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.ring-unit {
  font-size: 22px;
  font-weight: var(--fw-semibold);
  color: var(--label-secondary);
  margin-left: 2px;
}
.ring-cap {
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
  margin-top: 6px;
  letter-spacing: 0.3px;
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

/* 改进建议卡（分段落，语义色左边） */
.suggestion-card { overflow: hidden; }
.suggestion-item {
  display: flex;
  gap: 14px;
  padding: 16px 20px;
  position: relative;
}
.suggestion-item.has-sep::after {
  content: ''; position: absolute; left: 20px; right: 0; bottom: 0;
  height: 1px; background: var(--label-quaternary);
}
.suggestion-icon {
  font-size: 22px;
  line-height: 1.4;
  flex-shrink: 0;
  width: 28px;
  text-align: center;
}
.suggestion-body { flex: 1; }
.suggestion-title { font-size: var(--fs-body); font-weight: var(--fw-semibold); margin-bottom: 4px; }
.suggestion-text { font-size: var(--fs-subhead); color: var(--label); line-height: 1.6; opacity: 0.85; }

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
