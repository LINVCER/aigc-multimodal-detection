<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTaskDetail, requestHumanize, downloadReportPdf, getTaskCompare } from '@/api/detect'
import Skeleton from '@/components/Skeleton.vue'
import FeedbackDialog from '@/components/FeedbackDialog.vue'
import AssistantDrawer from '@/components/AssistantDrawer.vue'
import type { TaskDetail, ParagraphResult, TaskCompare } from '@/api/types'

const feedbackOpen = ref(false)
// 论文检测助手抽屉；assistantParagraph 非空时打开即自动追问该段
const assistantOpen = ref(false)
// 首次看到 DONE 报告时，助手主动打个招呼（只弹一次，按浏览器记）
const assistantTipDismissed = ref<boolean>(!!localStorage.getItem('assistant_tip_shown'))
const showAssistantTip = computed(() => detail.value?.status === 'DONE' && !assistantTipDismissed.value)
function dismissAssistantTip(go: boolean) {
  assistantTipDismissed.value = true
  try { localStorage.setItem('assistant_tip_shown', '1') } catch { /* ignore */ }
  if (go) openAssistant()
}
const assistantParagraph = ref<number | null>(null)
function openAssistant(paragraphIdx?: number) {
  assistantParagraph.value = paragraphIdx ?? null
  assistantOpen.value = true
}

const props = defineProps<{ id: string }>()
const router = useRouter()

const detail = ref<TaskDetail | null>(null)
const loading = ref(true)
const rewrittenMap = ref<Record<number, string>>({})
const humanizingMap = ref<Record<number, boolean>>({})
let pollTimer: any = null

// 降 AIGC 改写状态待定（监管定性未确认）：接口与后端链路保留，前端入口暂不放出
const ENABLE_HUMANIZE: boolean = false

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

/* 复测对比视图（product-feature-plan §2.2） */
const compareOpen = ref(false)
const compareLoading = ref(false)
const compareData = ref<TaskCompare | null>(null)
const COMPARE_STATUS: Record<string, { text: string; type: 'success' | 'danger' | 'info' | 'warning' }> = {
  down: { text: '降了', type: 'success' }, up: { text: '涨了', type: 'danger' }, same: { text: '持平', type: 'info' },
  added: { text: '新增段', type: 'warning' }, removed: { text: '已删段', type: 'info' },
}
async function openCompare() {
  compareOpen.value = true
  if (compareData.value) return
  compareLoading.value = true
  try { compareData.value = await getTaskCompare(Number(props.id)) }
  catch { compareOpen.value = false }
  finally { compareLoading.value = false }
}
const pct = (v: number | null | undefined) => (v == null ? '—' : Math.round(v * 100) + '%')
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

// 视图切换：段落顺序 / 按章节聚合
const paragraphView = ref<'paragraph' | 'section'>('paragraph')
const expandedSectionMap = ref<Record<string, boolean>>({})

interface SectionAgg {
  name: string
  paragraphs: ParagraphResult[]
  bodyCount: number
  excludedCount: number
  avgRate: number | null       // 该章正文段 AI 率平均
  maxRate: number              // 该章正文段最高 AI 率（用于染色）
}

const sectionGroups = computed<SectionAgg[]>(() => {
  const paragraphs = detail.value?.paragraphs || []
  if (paragraphs.length === 0) return []
  const map = new Map<string, ParagraphResult[]>()
  const order: string[] = []          // 保持章节出现顺序
  for (const p of paragraphs) {
    const key = p.sectionName || '正文'
    if (!map.has(key)) { map.set(key, []); order.push(key) }
    map.get(key)!.push(p)
  }
  return order.map(name => {
    const items = map.get(name)!
    const bodyItems = items.filter(p => !p.excluded && p.calibratedProb != null)
    const sum = bodyItems.reduce((s, p) => s + (p.calibratedProb || 0), 0)
    const avg = bodyItems.length ? (sum / bodyItems.length) * 100 : null
    const max = bodyItems.reduce((m, p) => Math.max(m, (p.calibratedProb || 0) * 100), 0)
    return {
      name,
      paragraphs: items,
      bodyCount: bodyItems.length,
      excludedCount: items.length - bodyItems.length,
      avgRate: avg,
      maxRate: max,
    }
  })
})

function sectionAvgColor(agg: SectionAgg): string {
  if (agg.avgRate == null) return 'var(--label-tertiary)'
  const thr = detail.value?.threshold ?? 20
  if (agg.avgRate <= thr) return 'var(--system-green)'
  if (agg.avgRate <= thr * 1.5) return 'var(--system-orange)'
  return 'var(--system-red)'
}

function toggleSection(name: string) {
  expandedSectionMap.value[name] = !expandedSectionMap.value[name]
}

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
        <div v-if="detail && detail.status === 'DONE'" class="header-actions">
          <el-button link size="small" @click="openAssistant()">💬 问助手</el-button>
          <el-button link size="small" @click="feedbackOpen = true">🚩 申诉</el-button>
          <el-button
            type="primary" round size="small"
            :loading="downloading" @click="onDownloadPdf"
          >⬇  下载 PDF</el-button>
        </div>
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
              <div v-if="detail.parentTaskId && detail.parentAiRate != null && detail.aiRate != null" class="hero-compare">
                <span :class="detail.aiRate <= detail.parentAiRate ? 'cmp-down' : 'cmp-up'">
                  比上次 {{ detail.aiRate <= detail.parentAiRate ? '−' : '+' }}{{ Math.abs(detail.aiRate - detail.parentAiRate).toFixed(1) }}%
                </span>
                <span class="cmp-sub">
                  上次 <router-link :to="{ name: 'TaskDetail', params: { id: detail.parentTaskId } }">#{{ detail.parentTaskId }}</router-link> {{ detail.parentAiRate.toFixed(1) }}%<template v-if="detail.parentModelVersion && detail.parentModelVersion !== detail.modelVersion">，模型已更新，不可直接比较</template>
                </span>
                <el-button link type="primary" size="small" @click="openCompare">查看段级对比 ›</el-button>
              </div>
              <div class="hero-paper">{{ detail.paperTitle }}</div>
              <div v-if="showAssistantTip" class="assist-tip">
                <span class="assist-tip-avatar">AI</span>
                <span class="assist-tip-text" @click="dismissAssistantTip(true)">
                  {{ pass ? '达标了。要不要我说说哪几段还是偏「机器」，下次写得更稳？' : '别急，超标不等于作弊。要我带你看哪几段贡献最大、先改哪段吗？' }}
                  <b>和助手聊聊 ›</b>
                </span>
                <el-button link size="small" @click.stop="dismissAssistantTip(false)">✕</el-button>
              </div>
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
              <div class="header-right">
                <!-- View toggle：段落顺序 / 章节聚合 -->
                <el-radio-group v-model="paragraphView" size="small" style="margin-right: 12px">
                  <el-radio-button label="paragraph" value="paragraph">段落</el-radio-button>
                  <el-radio-button label="section"   value="section">章节</el-radio-button>
                </el-radio-group>
                <div class="legend">
                  <span><span class="swatch high"></span> 高</span>
                  <span><span class="swatch mid"></span> 中</span>
                </div>
              </div>
            </div>

            <!-- ===== 章节视图 ===== -->
            <template v-if="paragraphView === 'section'">
              <el-card
                v-for="agg in sectionGroups" :key="agg.name"
                class="section-card"
                body-style="padding: 0"
              >
                <div class="section-head" @click="toggleSection(agg.name)">
                  <div class="section-head-left">
                    <div class="section-name">{{ agg.name }}</div>
                    <div class="section-meta">
                      <span>{{ agg.bodyCount }} 段正文</span>
                      <template v-if="agg.excludedCount > 0"><span class="dot">·</span>{{ agg.excludedCount }} 段已排除</template>
                    </div>
                  </div>
                  <div class="section-head-right">
                    <div class="section-rate" :style="{ color: sectionAvgColor(agg) }">
                      <template v-if="agg.avgRate != null">
                        {{ agg.avgRate.toFixed(0) }}<span class="section-rate-unit">%</span>
                      </template>
                      <template v-else>—</template>
                    </div>
                    <span class="section-chevron" :class="{ expanded: expandedSectionMap[agg.name] }">›</span>
                  </div>
                </div>

                <!-- 展开：该章段落列表（简版：段号+AI率+首 80 字） -->
                <div v-if="expandedSectionMap[agg.name]" class="section-body">
                  <div
                    v-for="p in agg.paragraphs" :key="p.paragraphIdx"
                    class="section-para" :class="{ excluded: p.excluded }"
                  >
                    <div class="section-para-head">
                      <span class="section-para-idx">段 {{ p.paragraphIdx + 1 }}</span>
                      <span v-if="p.excluded" class="excluded-badge">
                        {{ EXCLUDE_REASON_LABEL[p.excludeReason || ''] || '非正文' }}
                      </span>
                      <span
                        v-else
                        class="section-para-rate"
                        :style="{ color: paragraphProbColor(p.calibratedProb || 0) }"
                      >
                        {{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%
                      </span>
                    </div>
                    <div class="section-para-text">
                      {{ (p.text || '').slice(0, 80) }}{{ (p.text || '').length > 80 ? '…' : '' }}
                    </div>
                  </div>
                </div>
              </el-card>
            </template>

            <!-- ===== 段落视图（原样，保留完整交互） ===== -->
            <template v-else>

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
                v-if="!p.excluded && (p.calibratedProb || 0) >= 0.5"
                link type="primary" size="small" style="margin-top: 10px"
                @click="openAssistant(p.paragraphIdx)"
              >💬 为什么这段像 AI？</el-button>

              <el-button
                v-if="ENABLE_HUMANIZE && !p.excluded && (p.calibratedProb || 0) >= 0.7 && !rewrittenMap[p.paragraphIdx]"
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
          </template>
        </div>
      </template>
    </el-main>

    <FeedbackDialog v-model="feedbackOpen" :task-id="Number(id)" default-category="appeal" :paragraphs="detail?.paragraphs" />

    <!-- 复测对比 -->
    <el-dialog v-model="compareOpen" width="820" title="与上次检测对比" align-center>
      <div v-loading="compareLoading" class="cmp">
        <template v-if="compareData">
          <el-alert :type="compareData.comparable ? (compareData.summary.pass ? 'success' : 'warning') : 'info'" :closable="false" show-icon :title="compareData.summary.headline" />
          <div class="cmp-sides">
            <div class="cmp-side">
              <div class="cmp-side-label">上次 · #{{ compareData.parent.id }}</div>
              <div class="cmp-side-rate">{{ compareData.parent.aiRate == null ? '—' : compareData.parent.aiRate.toFixed(1) + '%' }}</div>
              <div class="cmp-side-sub">{{ compareData.parent.bodyParagraphs }} 段正文 · {{ compareData.parent.modelVersion }}</div>
            </div>
            <div class="cmp-arrow">→</div>
            <div class="cmp-side">
              <div class="cmp-side-label">本次 · #{{ compareData.current.id }}</div>
              <div class="cmp-side-rate" :class="compareData.summary.pass ? 'ok' : 'bad'">{{ compareData.current.aiRate == null ? '—' : compareData.current.aiRate.toFixed(1) + '%' }}</div>
              <div class="cmp-side-sub">{{ compareData.current.bodyParagraphs }} 段正文 · {{ compareData.current.modelVersion }} · 红线 {{ compareData.current.threshold }}%</div>
            </div>
          </div>
          <div class="cmp-stats">
            <el-tag type="success" size="small">降了 {{ compareData.summary.down }}</el-tag>
            <el-tag type="danger" size="small">涨了 {{ compareData.summary.up }}</el-tag>
            <el-tag type="warning" size="small">新增 {{ compareData.summary.added }}</el-tag>
            <el-tag type="info" size="small">删除 {{ compareData.summary.removed }}</el-tag>
          </div>
          <el-table :data="compareData.rows" size="small" max-height="420" :row-class-name="({ row }: any) => 'cmp-row-' + row.status">
            <el-table-column label="段" width="110">
              <template #default="{ row }">
                <span v-if="row.currIdx != null">本 {{ row.currIdx + 1 }}</span><span v-if="row.currIdx != null && row.parentIdx != null"> ← </span><span v-if="row.parentIdx != null">上 {{ row.parentIdx + 1 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="preview" label="内容" min-width="300" show-overflow-tooltip />
            <el-table-column label="上次" width="70"><template #default="{ row }">{{ pct(row.parentProb) }}</template></el-table-column>
            <el-table-column label="本次" width="70"><template #default="{ row }">{{ pct(row.currProb) }}</template></el-table-column>
            <el-table-column label="变化" width="110">
              <template #default="{ row }">
                <el-tag :type="COMPARE_STATUS[row.status]?.type" size="small">{{ COMPARE_STATUS[row.status]?.text }}<template v-if="row.delta != null"> {{ row.delta > 0 ? '+' : '' }}{{ Math.round(row.delta * 100) }}pp</template></el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div class="cmp-foot">段落按文本相似度配对；改动很大的段会分别算作「新增」和「删除」。</div>
        </template>
      </div>
    </el-dialog>
    <AssistantDrawer v-model="assistantOpen" :task-id="Number(id)" :paragraph-idx="assistantParagraph" />
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
.header-actions { display: flex; align-items: center; gap: 12px; }

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
.hero-compare { margin-top: 10px; display: flex; flex-direction: column; align-items: center; gap: 2px; }
.cmp { display: flex; flex-direction: column; gap: 12px; }
.cmp-sides { display: flex; align-items: center; justify-content: center; gap: 24px; }
.cmp-side { text-align: center; }
.cmp-side-label { font-size: 12px; color: rgba(60,60,67,0.60); }
.cmp-side-rate { font-size: 28px; font-weight: 600; letter-spacing: -0.5px; }
.cmp-side-rate.ok { color: #1B7F3E; } .cmp-side-rate.bad { color: #C62A22; }
.cmp-side-sub { font-size: 12px; color: rgba(60,60,67,0.60); }
.cmp-arrow { font-size: 24px; color: rgba(60,60,67,0.30); }
.cmp-stats { display: flex; gap: 8px; justify-content: center; }
.cmp-foot { font-size: 12px; color: rgba(60,60,67,0.60); }
:deep(.cmp-row-down) { background: rgba(52,199,89,0.06); }
:deep(.cmp-row-up) { background: rgba(255,59,48,0.06); }
.cmp-down { color: #1B7F3E; font-weight: 600; }
.cmp-up { color: #C62A22; font-weight: 600; }
.cmp-sub { font-size: 12px; color: rgba(60,60,67,0.60); }
.assist-tip {
  margin-top: 14px; padding: 10px 12px; border-radius: 10px;
  background: rgba(0, 122, 255, 0.08);
  display: flex; align-items: center; gap: 10px; text-align: left;
}
.assist-tip-avatar {
  flex: none; width: 26px; height: 26px; border-radius: 50%;
  background: linear-gradient(135deg, #5E5CE6 0%, #64D2FF 100%);
  color: #fff; font-size: 10px; font-weight: 700;
  display: inline-flex; align-items: center; justify-content: center;
}
.assist-tip-text { flex: 1; font-size: 13px; line-height: 1.5; cursor: pointer; }
.assist-tip-text b { color: var(--el-color-primary); margin-left: 6px; font-weight: 600; }
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

/* 段落分析头部：右侧放 view toggle + legend */
.header-right { display: flex; align-items: center; gap: 12px; padding-right: 12px; }

/* ============ 章节视图 ============ */
.section-card { margin-top: 12px; overflow: hidden; }

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  cursor: pointer;
  transition: background var(--dur-fast);
}
.section-head:hover { background: rgba(60, 60, 67, 0.06); }

.section-head-left { flex: 1; min-width: 0; }
.section-name {
  font-size: var(--fs-body);
  font-weight: var(--fw-semibold);
  color: var(--label);
  letter-spacing: -0.2px;
}
.section-meta {
  margin-top: 4px;
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
}
.section-meta .dot { margin: 0 6px; opacity: 0.4; }

.section-head-right {
  display: flex;
  align-items: center;
  gap: 16px;
}
.section-rate {
  font-size: 28px;
  font-weight: var(--fw-bold);
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.section-rate-unit {
  font-size: 14px;
  font-weight: var(--fw-semibold);
  color: var(--label-secondary);
  margin-left: 1px;
}
.section-chevron {
  color: var(--label-tertiary);
  font-size: 22px;
  line-height: 1;
  transition: transform var(--dur-base) var(--ease-standard);
}
.section-chevron.expanded { transform: rotate(90deg); }

.section-body {
  padding: 8px 20px 16px;
  border-top: 1px solid var(--label-quaternary);
  background: rgba(60, 60, 67, 0.03);
}
.section-para {
  padding: 10px 0;
  border-bottom: 1px solid var(--label-quaternary);
}
.section-para:last-child { border-bottom: none; }
.section-para.excluded { opacity: 0.65; }
.section-para-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.section-para-idx {
  font-size: 11px;
  font-weight: var(--fw-semibold);
  color: var(--label-secondary);
  letter-spacing: 0.6px;
  text-transform: uppercase;
}
.section-para-rate {
  font-size: var(--fs-footnote);
  font-weight: var(--fw-semibold);
  font-variant-numeric: tabular-nums;
}
.section-para-text {
  font-size: var(--fs-subhead);
  color: var(--label);
  line-height: 1.55;
}

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
