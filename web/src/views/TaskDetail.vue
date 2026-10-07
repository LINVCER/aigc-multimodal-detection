<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTaskDetail, downloadReportPdf, getTaskCompare, retryTask } from '@/api/detect'
import Skeleton from '@/components/Skeleton.vue'
import FeedbackDialog from '@/components/FeedbackDialog.vue'
import AssistantDrawer from '@/components/AssistantDrawer.vue'
import type { TaskDetail, ParagraphResult, TaskCompare } from '@/api/types'

/**
 * 检测报告页（重构版）
 *   顶栏：滚过 hero 后显示 AI 率 pill；问助手 / 申诉 / 下载
 *   主列：hero（环 + 达标 + 红黄绿分布 + 比上次）→ 先改这几段 → 改进建议 → 段落（筛选 / 段落·章节视图 / 全部展开）
 *   侧栏（≥ 1000px 固定）：摘要 · 来源分布 · 快捷动作
 *   处理中：四步进度按时间推进
 */

const props = defineProps<{ id: string }>()
const router = useRouter()

const feedbackOpen = ref(false)
const assistantOpen = ref(false)
const assistantParagraph = ref<number | null>(null)
function openAssistant(paragraphIdx?: number) { assistantParagraph.value = paragraphIdx ?? null; assistantOpen.value = true }
const assistantTipDismissed = ref<boolean>(!!localStorage.getItem('assistant_tip_shown'))
const showAssistantTip = computed(() => detail.value?.status === 'DONE' && !assistantTipDismissed.value)
function dismissAssistantTip(go: boolean) {
  assistantTipDismissed.value = true
  try { localStorage.setItem('assistant_tip_shown', '1') } catch { /* ignore */ }
  if (go) openAssistant()
}

const detail = ref<TaskDetail | null>(null)
const loading = ref(true)
let pollTimer: any = null
let startedAt = Date.now()
const elapsed = ref(0)
const compact = ref(false)

const SOURCE_LABEL: Record<string, string> = { human: '人类', gpt: 'GPT', claude: 'Claude', qwen: '通义千问', deepseek: 'DeepSeek', glm: '智谱GLM', kimi: 'Kimi', ernie: '文心', other: '其他' }
const SOURCE_COLOR: Record<string, string> = {
  human: 'var(--system-green)', gpt: 'var(--system-purple)', claude: 'var(--system-pink)', qwen: 'var(--system-orange)',
  deepseek: 'var(--system-blue)', glm: 'var(--system-teal)', kimi: 'var(--system-purple)', ernie: 'var(--system-red)', other: 'var(--system-gray)',
}
const EXCLUDE_REASON_LABEL: Record<string, string> = { reference: '参考文献', acknowledgement: '致谢', appendix: '附录', sectionTitle: '章节标题', caption: '图表标题' }
const STEPS = ['上传完成', '解析段落', '模型推理', '汇总报告']
const stepIndex = computed(() => (elapsed.value < 3 ? 1 : elapsed.value < 10 ? 2 : 3))

async function load() {
  try { detail.value = await getTaskDetail(Number(props.id)) }
  catch { /* toast 由拦截器给 */ }
  finally { loading.value = false }
}
function shouldPoll() { return detail.value && (detail.value.status === 'PENDING' || detail.value.status === 'RUNNING') }
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(async () => { elapsed.value = Math.floor((Date.now() - startedAt) / 1000); await load(); if (!shouldPoll()) stopPolling() }, 3000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
function onScroll() { compact.value = window.scrollY > 320 }
onMounted(async () => {
  await load()
  const t = detail.value?.createdAt ? Date.parse(String(detail.value.createdAt).replace(' ', 'T')) : NaN
  if (!Number.isNaN(t)) startedAt = t
  if (shouldPoll()) startPolling()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onUnmounted(() => { stopPolling(); window.removeEventListener('scroll', onScroll) })

const retrying = ref(false)
async function onRetry() {
  retrying.value = true
  try { await retryTask(Number(props.id)); ElMessage.success('已重新提交'); startedAt = Date.now(); await load(); if (shouldPoll()) startPolling() }
  finally { retrying.value = false }
}

/* ---------- 派生 ---------- */
const pass = computed(() => { const d = detail.value; return !!(d && d.aiRate != null && d.aiRate <= d.threshold) })
const summaryColor = computed(() => {
  const d = detail.value
  if (!d || d.aiRate == null) return 'var(--label-tertiary)'
  if (d.aiRate <= d.threshold) return 'var(--system-green)'
  if (d.aiRate <= d.threshold * 1.5) return 'var(--system-orange)'
  return 'var(--system-red)'
})
const ringCircumference = 2 * Math.PI * 86
const ringOffset = computed(() => { const d = detail.value; if (!d || d.aiRate == null) return ringCircumference; return ringCircumference * (1 - Math.min(100, Math.max(0, d.aiRate)) / 100) })
const ringThresholdOffset = computed(() => { const d = detail.value; if (!d || d.threshold == null) return ringCircumference; return ringCircumference * (1 - Math.min(100, Math.max(0, d.threshold)) / 100) })
const sortedSources = computed(() => Object.entries(detail.value?.sourceLabels || {}).sort(([, a], [, b]) => b - a).map(([label, ratio]) => ({ label, ratio })))
const bodyParas = computed(() => (detail.value?.paragraphs || []).filter((p) => !p.excluded))
const bodyStats = computed(() => {
  const all = detail.value?.paragraphs || []
  if (!all.length) return null
  return { body: bodyParas.value.length, excluded: all.length - bodyParas.value.length }
})
const dist = computed(() => {
  const ps = bodyParas.value
  const high = ps.filter((p) => (p.calibratedProb || 0) >= 0.7).length
  const mid = ps.filter((p) => { const v = p.calibratedProb || 0; return v >= 0.4 && v < 0.7 }).length
  const low = ps.length - high - mid
  const n = Math.max(1, ps.length)
  return { high, mid, low, highPct: (high / n) * 100, midPct: (mid / n) * 100, lowPct: (low / n) * 100 }
})
const priority = computed(() => bodyParas.value.filter((p) => (p.calibratedProb || 0) >= 0.5).sort((a, b) => (b.calibratedProb || 0) - (a.calibratedProb || 0)).slice(0, 3))

function sentenceBg(prob: number) { return prob >= 0.7 ? 'rgba(255, 59, 48, 0.14)' : prob >= 0.4 ? 'rgba(255, 149, 0, 0.16)' : 'transparent' }
function probColor(prob: number) { return prob >= 0.7 ? 'var(--system-red)' : prob >= 0.4 ? 'var(--system-orange)' : 'var(--system-green)' }

/* 段落筛选 / 视图 / 展开 */
type Filter = 'all' | 'high' | 'mid' | 'low' | 'excluded'
const paraFilter = ref<Filter>('all')
const paragraphView = ref<'paragraph' | 'section'>('paragraph')
const expandedMap = ref<Record<number, boolean>>({})
const allExpanded = ref(true)
const filteredParas = computed(() => {
  const all = detail.value?.paragraphs || []
  switch (paraFilter.value) {
    case 'high': return all.filter((p) => !p.excluded && (p.calibratedProb || 0) >= 0.7)
    case 'mid': return all.filter((p) => { const v = p.calibratedProb || 0; return !p.excluded && v >= 0.4 && v < 0.7 })
    case 'low': return all.filter((p) => !p.excluded && (p.calibratedProb || 0) < 0.4)
    case 'excluded': return all.filter((p) => p.excluded)
    default: return all
  }
})
const FILTERS = computed(() => [
  { key: 'all' as Filter, label: '全部', n: (detail.value?.paragraphs || []).length },
  { key: 'high' as Filter, label: '高', n: dist.value.high, cls: 'high' },
  { key: 'mid' as Filter, label: '中', n: dist.value.mid, cls: 'mid' },
  { key: 'low' as Filter, label: '低', n: dist.value.low, cls: 'low' },
  { key: 'excluded' as Filter, label: '已排除', n: bodyStats.value?.excluded || 0 },
])
function isExpanded(idx: number) { return expandedMap.value[idx] ?? allExpanded.value }
function toggleExpand(idx: number) { expandedMap.value[idx] = !isExpanded(idx) }
function toggleAll() { allExpanded.value = !allExpanded.value; expandedMap.value = {} }
function jumpTo(idx: number) {
  paraFilter.value = 'all'; paragraphView.value = 'paragraph'; expandedMap.value[idx] = true
  setTimeout(() => document.getElementById('para-' + idx)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
}
function goSection(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }) }
async function copyText(text: string) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('已复制') } catch { ElMessage.warning('复制失败') }
}

/* 章节视图 */
interface SectionAgg { name: string; paragraphs: ParagraphResult[]; bodyCount: number; excludedCount: number; avgRate: number | null }
const sectionGroups = computed<SectionAgg[]>(() => {
  const paragraphs = detail.value?.paragraphs || []
  const map = new Map<string, ParagraphResult[]>()
  const order: string[] = []
  for (const p of paragraphs) {
    const key = p.sectionName || '正文'
    if (!map.has(key)) { map.set(key, []); order.push(key) }
    map.get(key)!.push(p)
  }
  return order.map((name) => {
    const items = map.get(name)!
    const body = items.filter((p) => !p.excluded && p.calibratedProb != null)
    const avg = body.length ? (body.reduce((s, p) => s + (p.calibratedProb || 0), 0) / body.length) * 100 : null
    return { name, paragraphs: items, bodyCount: body.length, excludedCount: items.length - body.length, avgRate: avg }
  })
})
const expandedSectionMap = ref<Record<string, boolean>>({})
function sectionColor(agg: SectionAgg) {
  if (agg.avgRate == null) return 'var(--label-tertiary)'
  const thr = detail.value?.threshold ?? 20
  return agg.avgRate <= thr ? 'var(--system-green)' : agg.avgRate <= thr * 1.5 ? 'var(--system-orange)' : 'var(--system-red)'
}

/* 建议 */
const suggestions = computed<Array<{ title: string; body: string; severity: 'info' | 'warn' | 'danger' | 'success' }>>(() => {
  const d = detail.value
  if (!d || d.status !== 'DONE' || d.aiRate == null) return []
  const out: Array<{ title: string; body: string; severity: 'info' | 'warn' | 'danger' | 'success' }> = []
  if (d.aiRate > d.threshold) out.push({ title: `AI 率超线 ${(d.aiRate - d.threshold).toFixed(1)} 个百分点`, body: `${d.aiRate.toFixed(1)}% 超过 ${d.threshold}% 红线。优先处理「先改这几段」，用自己的话重写核心观点，补具体数据和真实经历。`, severity: 'danger' })
  else if (d.aiRate > d.threshold * 0.7) out.push({ title: '接近红线，仍有修改空间', body: `AI 率 ${d.aiRate.toFixed(1)}%，距 ${d.threshold}% 红线不足 ${(d.threshold - d.aiRate).toFixed(1)} 个百分点。对标黄段落做小幅改写，留出安全缓冲。`, severity: 'warn' })
  else out.push({ title: '整体达标', body: `AI 率 ${d.aiRate.toFixed(1)}%，明显低于 ${d.threshold}% 红线。继续保持原创性写作。`, severity: 'success' })
  if (d.sourceLabels) {
    const entries = Object.entries(d.sourceLabels).filter(([k]) => k !== 'human').sort((a, b) => b[1] - a[1])
    if (entries.length && entries[0][1] >= 0.4) {
      const src = SOURCE_LABEL[entries[0][0]] || entries[0][0]
      out.push({ title: `疑似大量使用 ${src}`, body: `${(entries[0][1] * 100).toFixed(0)}% 段落被判为 ${src} 风格。避免连续段落使用同一 AI 助手，改写时调整句式节奏。`, severity: 'info' })
    }
  }
  if (bodyStats.value && bodyStats.value.excluded > bodyStats.value.body) out.push({ title: '识别到大量非正文段落', body: `${bodyStats.value.excluded} 段被识别为参考文献 / 图表 / 章节标题，未参与计算。若不符合预期请检查论文格式。`, severity: 'info' })
  return out
})
const SEV: Record<string, { fg: string; bg: string }> = {
  danger: { fg: 'var(--system-red)', bg: 'rgba(255, 59, 48, 0.08)' }, warn: { fg: 'var(--system-orange)', bg: 'rgba(255, 149, 0, 0.08)' },
  success: { fg: 'var(--system-green)', bg: 'rgba(52, 199, 89, 0.08)' }, info: { fg: 'var(--system-blue)', bg: 'rgba(0, 122, 255, 0.06)' },
}

/* 下载 / 对比 */
const downloading = ref(false)
async function onDownloadPdf() {
  if (!detail.value) return
  downloading.value = true
  try { await downloadReportPdf(Number(props.id), detail.value.paperTitle); ElMessage.success('报告已下载') }
  catch (e: any) { ElMessage.error(e?.message || '下载失败') }
  finally { downloading.value = false }
}
const compareOpen = ref(false)
const compareLoading = ref(false)
const compareData = ref<TaskCompare | null>(null)
const COMPARE_STATUS: Record<string, { text: string; type: 'success' | 'danger' | 'info' | 'warning' }> = {
  down: { text: '降了', type: 'success' }, up: { text: '涨了', type: 'danger' }, same: { text: '持平', type: 'info' }, added: { text: '新增段', type: 'warning' }, removed: { text: '已删段', type: 'info' },
}
async function openCompare() {
  compareOpen.value = true
  if (compareData.value) return
  compareLoading.value = true
  try { compareData.value = await getTaskCompare(Number(props.id)) } catch { compareOpen.value = false } finally { compareLoading.value = false }
}
const pct = (v: number | null | undefined) => (v == null ? '—' : Math.round(v * 100) + '%')
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <div class="header-mid">
          <span class="header-title">检测报告</span>
          <transition name="fade">
            <span v-if="compact && detail?.status === 'DONE'" class="header-pill">
              <span class="header-pill-rate" :style="{ color: summaryColor }">{{ detail?.aiRate?.toFixed(1) }}%</span>
              <span class="header-pill-badge" :class="pass ? 'ok' : 'bad'">{{ pass ? '达标' : '超线' }}</span>
            </span>
          </transition>
        </div>
        <div v-if="detail && detail.status === 'DONE'" class="header-actions">
          <el-button link size="small" @click="openAssistant()">💬 问助手</el-button>
          <el-button link size="small" @click="feedbackOpen = true">🚩 申诉</el-button>
          <el-button type="primary" round size="small" :loading="downloading" @click="onDownloadPdf">⬇ 下载 PDF</el-button>
        </div>
        <span v-else></span>
      </div>
    </el-header>

    <el-main class="main">
      <Skeleton v-if="loading" :rows="4" />

      <template v-else-if="detail">
        <!-- ================= 处理中 / 失败 ================= -->
        <div v-if="detail.status === 'PENDING' || detail.status === 'RUNNING'" class="wrap-narrow">
          <div class="state">
            <div class="spinner" />
            <div class="state-title warn">检测中</div>
            <div class="state-sub">通常 15–30 秒，页面会自动刷新</div>
            <div class="steps">
              <div v-for="(s, i) in STEPS" :key="s" class="step" :class="{ done: i < stepIndex, now: i === stepIndex }"><i /><span>{{ s }}</span></div>
            </div>
            <div class="state-paper">{{ detail.paperTitle }}</div>
          </div>
        </div>
        <div v-else-if="detail.status === 'FAILED'" class="wrap-narrow">
          <div class="state">
            <div class="xmark">✕</div>
            <div class="state-title bad">检测失败</div>
            <div class="state-sub">推理服务暂时不可用，或文件无法解析出正文</div>
            <el-button type="primary" round :loading="retrying" @click="onRetry">重新检测</el-button>
          </div>
        </div>

        <!-- ================= 完成 ================= -->
        <div v-else class="wrap">
          <div class="col-main">
            <!-- hero -->
            <el-card id="sec-overview" class="hero" body-style="padding: 32px 32px 24px">
              <div class="hero-grid">
                <div class="ring-wrap">
                  <svg class="ring" viewBox="0 0 200 200">
                    <circle cx="100" cy="100" r="86" fill="none" stroke="rgba(120, 120, 128, 0.16)" stroke-width="14" />
                    <circle cx="100" cy="100" r="86" fill="none" :stroke="summaryColor" stroke-width="14" stroke-linecap="round" :stroke-dasharray="ringCircumference" :stroke-dashoffset="ringOffset" transform="rotate(-90 100 100)" style="transition: stroke-dashoffset 900ms cubic-bezier(0.32, 0.72, 0, 1)" />
                    <circle cx="100" cy="100" r="86" fill="none" :stroke="pass ? 'var(--system-green)' : 'var(--system-red)'" stroke-width="14" :stroke-dasharray="`3 ${ringCircumference - 3}`" :stroke-dashoffset="ringThresholdOffset" transform="rotate(-90 100 100)" opacity="0.9" />
                  </svg>
                  <div class="ring-center">
                    <div class="ring-label">整体 AI 率</div>
                    <div class="ring-rate" :style="{ color: summaryColor }">{{ detail.aiRate?.toFixed(1) }}<span class="ring-unit">%</span></div>
                    <div class="ring-cap">红线 {{ detail.threshold }}%</div>
                  </div>
                </div>
                <div class="hero-side">
                  <div class="verdict" :class="pass ? 'ok' : 'bad'">{{ pass ? '✓ 低于红线，达标' : '⚠ 超过红线 ' + (detail.aiRate! - detail.threshold).toFixed(1) + ' 个百分点' }}</div>
                  <div class="hero-paper">{{ detail.paperTitle }}</div>
                  <div v-if="bodyStats" class="dist">
                    <div class="dist-bar"><i class="high" :style="{ width: dist.highPct + '%' }" /><i class="mid" :style="{ width: dist.midPct + '%' }" /><i class="low" :style="{ width: dist.lowPct + '%' }" /></div>
                    <div class="dist-legend"><b class="high">高 {{ dist.high }}</b><b class="mid">中 {{ dist.mid }}</b><b class="low">低 {{ dist.low }}</b><span class="muted">正文 {{ bodyStats.body }} 段<template v-if="bodyStats.excluded"> · 排除 {{ bodyStats.excluded }}</template></span></div>
                  </div>
                  <div v-if="detail.parentTaskId && detail.parentAiRate != null && detail.aiRate != null" class="compare" @click="openCompare">
                    <b :class="detail.aiRate <= detail.parentAiRate ? 'down' : 'up'">比上次 {{ detail.aiRate <= detail.parentAiRate ? '−' : '+' }}{{ Math.abs(detail.aiRate - detail.parentAiRate).toFixed(1) }}%</b>
                    <span class="muted">上次 {{ detail.parentAiRate.toFixed(1) }}%<template v-if="detail.parentModelVersion && detail.parentModelVersion !== detail.modelVersion"> · 模型已更新，不可直接比较</template></span>
                    <span class="link">逐段对比 ›</span>
                  </div>
                  <div class="hero-actions">
                    <el-button type="primary" round @click="openAssistant()">💬 问助手解读</el-button>
                    <el-button round @click="goSection('sec-paras')">看段落</el-button>
                  </div>
                </div>
              </div>
              <div v-if="showAssistantTip" class="assist-tip">
                <img class="assist-tip-avatar" src="/xiaobai.gif" alt="小白" />
                <span class="assist-tip-text" @click="dismissAssistantTip(true)">{{ pass ? '达标了。要不要我说说哪几段还是偏「机器」，下次写得更稳？' : '别急，超标不等于作弊。要我带你看哪几段贡献最大、先改哪段吗？' }} <b>和助手聊聊 ›</b></span>
                <el-button link size="small" @click.stop="dismissAssistantTip(false)">✕</el-button>
              </div>
            </el-card>

            <!-- 锚点 -->
            <div class="anchors">
              <button class="anchor" @click="goSection('sec-overview')">概览</button>
              <button class="anchor" @click="goSection('sec-paras')">段落 {{ (detail.paragraphs || []).length }}</button>
              <button class="anchor" @click="goSection('sec-sources')">来源</button>
            </div>

            <!-- 先改这几段 -->
            <template v-if="priority.length">
              <div class="section-head"><span class="section-header">先改这几段</span><span class="section-sub">按贡献排序</span></div>
              <el-card class="prio" body-style="padding: 0">
                <div v-for="(p, i) in priority" :key="p.paragraphIdx" class="prio-item" @click="jumpTo(p.paragraphIdx)">
                  <span class="prio-rank" :style="{ background: probColor(p.calibratedProb || 0) }">{{ i + 1 }}</span>
                  <div class="prio-main">
                    <div class="prio-line"><span class="prio-idx">段 {{ p.paragraphIdx + 1 }}</span><b :style="{ color: probColor(p.calibratedProb || 0) }">{{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%</b><span v-if="p.sourceLabel && p.sourceLabel !== 'human'" class="muted">疑似 {{ SOURCE_LABEL[p.sourceLabel] || p.sourceLabel }}</span></div>
                    <div class="prio-preview">{{ (p.text || '').slice(0, 90) }}…</div>
                  </div>
                  <el-button link type="primary" size="small" @click.stop="openAssistant(p.paragraphIdx)">为什么</el-button>
                </div>
              </el-card>
            </template>

            <!-- 建议 -->
            <template v-if="suggestions.length">
              <div class="section-head"><span class="section-header">改进建议</span></div>
              <el-card class="sug-card" body-style="padding: 0">
                <div v-for="(s, i) in suggestions" :key="i" class="sug" :style="{ background: SEV[s.severity].bg }">
                  <i :style="{ background: SEV[s.severity].fg }" />
                  <div><div class="sug-title" :style="{ color: SEV[s.severity].fg }">{{ s.title }}</div><div class="sug-text">{{ s.body }}</div></div>
                </div>
              </el-card>
            </template>

            <!-- 段落 -->
            <div id="sec-paras" class="section-head">
              <span class="section-header">段落分析</span>
              <div class="section-tools">
                <el-radio-group v-model="paragraphView" size="small">
                  <el-radio-button value="paragraph">段落</el-radio-button>
                  <el-radio-button value="section">章节</el-radio-button>
                </el-radio-group>
                <el-button v-if="paragraphView === 'paragraph'" link size="small" @click="toggleAll">{{ allExpanded ? '全部收起' : '全部展开' }}</el-button>
              </div>
            </div>
            <div v-if="paragraphView === 'paragraph'" class="filters">
              <button v-for="f in FILTERS" :key="f.key" class="filter" :class="[{ active: paraFilter === f.key }, f.cls]" @click="paraFilter = f.key">{{ f.label }} <span class="filter-n">{{ f.n }}</span></button>
              <span class="legend"><i class="sw high" /> 高 ≥70% <i class="sw mid" /> 中 40–70% · 句子按概率着色</span>
            </div>

            <template v-if="paragraphView === 'section'">
              <el-card v-for="agg in sectionGroups" :key="agg.name" class="sec-card" body-style="padding: 0">
                <div class="sec-head" @click="expandedSectionMap[agg.name] = !expandedSectionMap[agg.name]">
                  <div><div class="sec-name">{{ agg.name }}</div><div class="muted small">{{ agg.bodyCount }} 段正文<template v-if="agg.excludedCount"> · {{ agg.excludedCount }} 段已排除</template></div></div>
                  <div class="sec-right"><b class="sec-rate" :style="{ color: sectionColor(agg) }">{{ agg.avgRate == null ? '—' : agg.avgRate.toFixed(0) + '%' }}</b><span class="chev" :class="{ open: expandedSectionMap[agg.name] }">›</span></div>
                </div>
                <div v-if="expandedSectionMap[agg.name]" class="sec-body">
                  <div v-for="p in agg.paragraphs" :key="p.paragraphIdx" class="sec-para" :class="{ excluded: p.excluded }" @click="jumpTo(p.paragraphIdx)">
                    <span class="para-idx">段 {{ p.paragraphIdx + 1 }}</span>
                    <span v-if="p.excluded" class="excluded-badge">{{ EXCLUDE_REASON_LABEL[p.excludeReason || ''] || '非正文' }}</span>
                    <b v-else :style="{ color: probColor(p.calibratedProb || 0) }">{{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%</b>
                    <span class="sec-para-text">{{ (p.text || '').slice(0, 80) }}…</span>
                  </div>
                </div>
              </el-card>
            </template>

            <template v-else>
              <div v-if="!filteredParas.length" class="empty">这一类没有段落</div>
              <el-card v-for="p in filteredParas" :key="p.paragraphIdx" :id="'para-' + p.paragraphIdx" class="para" :class="{ 'para-excluded': p.excluded }" body-style="padding: 0">
                <div class="para-header" @click="toggleExpand(p.paragraphIdx)">
                  <i class="para-bar" :style="{ background: p.excluded ? 'rgba(120,120,128,0.3)' : probColor(p.calibratedProb || 0) }" />
                  <span class="para-idx">段 {{ p.paragraphIdx + 1 }}</span>
                  <span v-if="p.excluded" class="excluded-badge">未参与计算 · {{ EXCLUDE_REASON_LABEL[p.excludeReason || ''] || '非正文' }}</span>
                  <b v-else class="para-prob" :style="{ color: probColor(p.calibratedProb || 0) }">{{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%<span v-if="p.sourceLabel && p.sourceLabel !== 'human'" class="muted"> · 疑似 {{ SOURCE_LABEL[p.sourceLabel] || p.sourceLabel }}</span></b>
                  <span v-if="p.sectionName" class="muted small">{{ p.sectionName }}</span>
                  <span class="flex-1" />
                  <span class="chev" :class="{ open: isExpanded(p.paragraphIdx) }">›</span>
                </div>
                <div v-if="!isExpanded(p.paragraphIdx)" class="para-preview" @click="toggleExpand(p.paragraphIdx)">{{ (p.text || '').slice(0, 120) }}{{ (p.text || '').length > 120 ? '…' : '' }}</div>
                <div v-else class="para-body">
                  <div v-if="p.excluded" class="para-excluded-text">{{ p.text }}</div>
                  <div v-else class="para-text"><span v-for="s in p.sentences" :key="s.sentenceIdx" :style="{ background: sentenceBg(s.aiProb) }">{{ s.text }}</span></div>
                  <div class="para-actions">
                    <el-button link size="small" @click="copyText(p.text)">复制</el-button>
                    <el-button v-if="!p.excluded && (p.calibratedProb || 0) >= 0.4" link type="primary" size="small" @click="openAssistant(p.paragraphIdx)">💬 为什么这段像 AI？</el-button>
                  </div>
                </div>
              </el-card>
            </template>

            <!-- 来源（窄屏时在主列） -->
            <div id="sec-sources" class="section-head only-narrow"><span class="section-header">疑似来源分布</span></div>
            <el-card class="sources only-narrow" body-style="padding: 8px 0">
              <div v-for="s in sortedSources" :key="s.label" class="source-item">
                <div class="source-line"><span class="source-name"><i :style="{ background: SOURCE_COLOR[s.label] || 'var(--system-gray)' }" />{{ SOURCE_LABEL[s.label] || s.label }}</span><b>{{ (s.ratio * 100).toFixed(0) }}%</b></div>
                <el-progress :percentage="Math.round(s.ratio * 100)" :stroke-width="8" :show-text="false" :color="SOURCE_COLOR[s.label] || 'var(--system-gray)'" />
              </div>
            </el-card>
            <div class="meta-line">模型 {{ detail.modelVersion || '—' }} · {{ detail.createdAt }} · 置信度仅供参考，建议人工复核</div>
          </div>

          <!-- 侧栏 -->
          <aside class="col-side">
            <div class="side-sticky">
              <el-card class="side-card" body-style="padding: 16px 18px">
                <div class="side-title">疑似来源分布</div>
                <div v-for="s in sortedSources" :key="s.label" class="source-item compact">
                  <div class="source-line"><span class="source-name"><i :style="{ background: SOURCE_COLOR[s.label] || 'var(--system-gray)' }" />{{ SOURCE_LABEL[s.label] || s.label }}</span><b>{{ (s.ratio * 100).toFixed(0) }}%</b></div>
                  <el-progress :percentage="Math.round(s.ratio * 100)" :stroke-width="6" :show-text="false" :color="SOURCE_COLOR[s.label] || 'var(--system-gray)'" />
                </div>
                <div v-if="!sortedSources.length" class="muted small">暂无溯源数据</div>
              </el-card>
              <el-card class="side-card" body-style="padding: 16px 18px">
                <div class="side-title">下一步</div>
                <div class="side-actions">
                  <el-button round @click="openAssistant()">💬 问助手为什么</el-button>
                  <el-button round @click="router.push('/upload')">↻ 修改后再测一次</el-button>
                  <el-button round @click="feedbackOpen = true">🚩 我觉得判错了</el-button>
                  <el-button round :loading="downloading" @click="onDownloadPdf">⬇ 下载 PDF 报告</el-button>
                </div>
              </el-card>
              <div class="side-note">助手只讲原则与方向，不代写、不改写原文。</div>
            </div>
          </aside>
        </div>
      </template>
    </el-main>

    <FeedbackDialog v-model="feedbackOpen" :task-id="Number(id)" default-category="appeal" :paragraphs="detail?.paragraphs" />
    <AssistantDrawer v-model="assistantOpen" :task-id="Number(id)" :paragraph-idx="assistantParagraph" />

    <!-- 复测对比 -->
    <el-dialog v-model="compareOpen" width="820" title="与上次检测对比" align-center>
      <div v-loading="compareLoading" class="cmp">
        <template v-if="compareData">
          <el-alert :type="compareData.comparable ? (compareData.summary.pass ? 'success' : 'warning') : 'info'" :closable="false" show-icon :title="compareData.summary.headline" />
          <div class="cmp-sides">
            <div class="cmp-side"><div class="muted small">上次 · #{{ compareData.parent.id }}</div><div class="cmp-side-rate">{{ compareData.parent.aiRate == null ? '—' : compareData.parent.aiRate.toFixed(1) + '%' }}</div><div class="muted small">{{ compareData.parent.bodyParagraphs }} 段正文 · {{ compareData.parent.modelVersion }}</div></div>
            <div class="cmp-arrow">→</div>
            <div class="cmp-side"><div class="muted small">本次 · #{{ compareData.current.id }}</div><div class="cmp-side-rate" :class="compareData.summary.pass ? 'ok' : 'bad'">{{ compareData.current.aiRate == null ? '—' : compareData.current.aiRate.toFixed(1) + '%' }}</div><div class="muted small">{{ compareData.current.bodyParagraphs }} 段正文 · {{ compareData.current.modelVersion }} · 红线 {{ compareData.current.threshold }}%</div></div>
          </div>
          <div class="cmp-stats">
            <el-tag type="success" size="small">降了 {{ compareData.summary.down }}</el-tag><el-tag type="danger" size="small">涨了 {{ compareData.summary.up }}</el-tag>
            <el-tag type="warning" size="small">新增 {{ compareData.summary.added }}</el-tag><el-tag type="info" size="small">删除 {{ compareData.summary.removed }}</el-tag>
          </div>
          <el-table :data="compareData.rows" size="small" max-height="420" :row-class-name="({ row }: any) => 'cmp-row-' + row.status">
            <el-table-column label="段" width="110"><template #default="{ row }"><span v-if="row.currIdx != null">本 {{ row.currIdx + 1 }}</span><span v-if="row.currIdx != null && row.parentIdx != null"> ← </span><span v-if="row.parentIdx != null">上 {{ row.parentIdx + 1 }}</span></template></el-table-column>
            <el-table-column prop="preview" label="内容" min-width="300" show-overflow-tooltip />
            <el-table-column label="上次" width="70"><template #default="{ row }">{{ pct(row.parentProb) }}</template></el-table-column>
            <el-table-column label="本次" width="70"><template #default="{ row }">{{ pct(row.currProb) }}</template></el-table-column>
            <el-table-column label="变化" width="110"><template #default="{ row }"><el-tag :type="COMPARE_STATUS[row.status]?.type" size="small">{{ COMPARE_STATUS[row.status]?.text }}<template v-if="row.delta != null"> {{ row.delta > 0 ? '+' : '' }}{{ Math.round(row.delta * 100) }}pp</template></el-tag></template></el-table-column>
          </el-table>
          <div class="muted small">段落按文本相似度配对；改动很大的段会分别算作「新增」和「删除」。</div>
        </template>
      </div>
    </el-dialog>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header { background: rgba(255, 255, 255, 0.78); backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid var(--label-quaternary); padding: 0; position: sticky; top: 0; z-index: 10; }
.header-inner { height: 56px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.header-mid { display: flex; align-items: center; gap: 10px; }
.header-title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }
.header-pill { display: inline-flex; align-items: center; gap: 6px; padding: 2px 10px; border-radius: 99px; background: rgba(120, 120, 128, 0.10); }
.header-pill-rate { font-weight: 700; font-variant-numeric: tabular-nums; }
.header-pill-badge { font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 99px; }
.header-pill-badge.ok { background: rgba(52, 199, 89, 0.14); color: #1B7F3E; } .header-pill-badge.bad { background: rgba(255, 59, 48, 0.14); color: #C62A22; }
.fade-enter-active, .fade-leave-active { transition: opacity .2s; } .fade-enter-from, .fade-leave-to { opacity: 0; }
.header-actions { display: flex; align-items: center; gap: 12px; }
.main { padding: 28px 24px 64px; }
.wrap { max-width: 1120px; margin: 0 auto; display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 24px; align-items: start; }
.wrap-narrow { max-width: 640px; margin: 0 auto; }
.only-narrow { display: none; }
@media (max-width: 1000px) { .wrap { grid-template-columns: 1fr; } .col-side { display: none; } .only-narrow { display: block; } }
.muted { color: var(--label-secondary); } .small { font-size: 12px; } .flex-1 { flex: 1; }

/* 状态 */
.state { background: #fff; border-radius: 16px; padding: 56px 32px 40px; text-align: center; box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04); }
.spinner { width: 56px; height: 56px; border-radius: 50%; border: 5px solid rgba(255, 149, 0, 0.18); border-top-color: var(--system-orange); animation: spin 1s linear infinite; margin: 0 auto; }
@keyframes spin { to { transform: rotate(360deg); } }
.xmark { width: 56px; height: 56px; border-radius: 50%; background: rgba(255, 59, 48, 0.12); color: var(--system-red); font-size: 26px; font-weight: 700; display: flex; align-items: center; justify-content: center; margin: 0 auto; }
.state-title { font-size: var(--fs-title-3); font-weight: 600; margin-top: 16px; }
.state-title.warn { color: var(--system-orange); } .state-title.bad { color: var(--system-red); }
.state-sub { color: var(--label-secondary); margin-top: 6px; }
.state-paper { font-size: 13px; color: var(--label-secondary); margin: 16px 0 12px; }
.steps { display: flex; justify-content: space-between; margin: 24px auto 0; max-width: 420px; }
.step { display: flex; flex-direction: column; align-items: center; gap: 6px; flex: 1; font-size: 12px; color: var(--label-tertiary); }
.step i { width: 10px; height: 10px; border-radius: 50%; background: rgba(120, 120, 128, 0.25); }
.step.done i { background: var(--system-green); } .step.done { color: var(--label-secondary); }
.step.now i { background: var(--system-orange); box-shadow: 0 0 0 4px rgba(255, 149, 0, 0.18); } .step.now { color: var(--system-orange); font-weight: 600; }

/* hero */
.hero-grid { display: grid; grid-template-columns: 220px 1fr; gap: 28px; align-items: center; }
@media (max-width: 640px) { .hero-grid { grid-template-columns: 1fr; justify-items: center; text-align: center; } }
.ring-wrap { position: relative; width: 220px; height: 220px; }
.ring { width: 100%; height: 100%; display: block; }
.ring-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.ring-label { font-size: 11px; color: var(--label-secondary); text-transform: uppercase; letter-spacing: .5px; }
.ring-rate { font-size: 52px; font-weight: 700; letter-spacing: -1.5px; line-height: 1; font-variant-numeric: tabular-nums; }
.ring-unit { font-size: 20px; font-weight: 600; color: var(--label-secondary); margin-left: 2px; }
.ring-cap { font-size: 12px; color: var(--label-secondary); margin-top: 6px; }
.hero-side { min-width: 0; }
.verdict { display: inline-block; padding: 6px 14px; border-radius: 99px; font-weight: 600; }
.verdict.ok { background: rgba(52, 199, 89, 0.14); color: #1B7F3E; } .verdict.bad { background: rgba(255, 59, 48, 0.14); color: #C62A22; }
.hero-paper { font-size: var(--fs-headline); font-weight: 600; margin-top: 10px; }
.dist { margin-top: 14px; }
.dist-bar { display: flex; height: 10px; border-radius: 99px; overflow: hidden; background: rgba(120, 120, 128, 0.12); }
.dist-bar i { height: 100%; } .dist-bar .high { background: var(--system-red); } .dist-bar .mid { background: var(--system-orange); } .dist-bar .low { background: var(--system-green); }
.dist-legend { display: flex; gap: 14px; margin-top: 6px; font-size: 12px; }
.dist-legend .high { color: #C62A22; } .dist-legend .mid { color: #B26200; } .dist-legend .low { color: #1B7F3E; } .dist-legend .muted { margin-left: auto; }
.compare { margin-top: 12px; padding: 8px 12px; border-radius: 10px; background: rgba(120, 120, 128, 0.08); display: flex; align-items: center; gap: 10px; font-size: 13px; cursor: pointer; }
.compare .down { color: #1B7F3E; } .compare .up { color: #C62A22; } .compare .link { margin-left: auto; color: var(--system-blue); font-weight: 500; }
.hero-actions { margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }
.assist-tip { margin-top: 18px; padding: 10px 12px; border-radius: 10px; background: rgba(0, 122, 255, 0.08); display: flex; align-items: center; gap: 10px; text-align: left; }
.assist-tip-avatar { flex: none; width: 26px; height: 26px; border-radius: 50%; background: linear-gradient(135deg, #5E5CE6 0%, #64D2FF 100%); color: #fff; font-size: 10px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.assist-tip-text { flex: 1; font-size: 13px; line-height: 1.5; cursor: pointer; } .assist-tip-text b { color: var(--system-blue); margin-left: 6px; }

/* 锚点 / section */
.anchors { display: flex; gap: 6px; margin: 14px 0 4px; padding: 3px; background: rgba(120, 120, 128, 0.10); border-radius: 10px; width: fit-content; }
.anchor { border: none; background: transparent; padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500; cursor: pointer; color: var(--label); }
.anchor:hover { background: #fff; }
.section-head { display: flex; justify-content: space-between; align-items: center; padding: 24px 4px 8px; }
.section-header { font-size: var(--fs-caption-1); font-weight: 500; color: var(--label-secondary); text-transform: uppercase; letter-spacing: .5px; }
.section-sub { font-size: 12px; color: var(--label-tertiary); }
.section-tools { display: flex; align-items: center; gap: 10px; }
.empty { text-align: center; color: var(--label-tertiary); padding: 32px 0; font-size: 13px; }

/* 先改这几段 */
.prio-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-bottom: 1px solid var(--label-quaternary); cursor: pointer; }
.prio-item:last-child { border-bottom: none; } .prio-item:hover { background: rgba(60, 60, 67, 0.04); }
.prio-rank { flex: none; width: 26px; height: 26px; border-radius: 50%; color: #fff; font-size: 12px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.prio-main { flex: 1; min-width: 0; }
.prio-line { display: flex; align-items: baseline; gap: 8px; font-size: 13px; }
.prio-idx { color: var(--label-secondary); font-weight: 600; }
.prio-preview { font-size: 13px; margin-top: 2px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

/* 建议 */
.sug { display: flex; gap: 12px; padding: 14px 18px; border-bottom: 1px solid var(--label-quaternary); }
.sug:last-child { border-bottom: none; }
.sug i { flex: none; width: 8px; height: 8px; border-radius: 50%; margin-top: 7px; }
.sug-title { font-weight: 600; margin-bottom: 3px; } .sug-text { font-size: 13px; line-height: 1.6; opacity: .85; }

/* 筛选 */
.filters { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-bottom: 8px; }
.filter { border: 1px solid var(--label-quaternary); background: #fff; border-radius: 99px; padding: 4px 12px; font-size: 13px; cursor: pointer; color: var(--label); }
.filter.active { background: var(--label); color: #fff; border-color: var(--label); }
.filter.high.active { background: var(--system-red); border-color: var(--system-red); } .filter.mid.active { background: var(--system-orange); border-color: var(--system-orange); } .filter.low.active { background: var(--system-green); border-color: var(--system-green); }
.filter-n { opacity: .7; font-size: 12px; }
.legend { margin-left: auto; font-size: 12px; color: var(--label-secondary); }
.sw { display: inline-block; width: 14px; height: 7px; border-radius: 2px; vertical-align: middle; } .sw.high { background: rgba(255, 59, 48, 0.3); } .sw.mid { background: rgba(255, 149, 0, 0.3); margin-left: 8px; }

/* 段落卡 */
.para { margin-top: 10px; overflow: hidden; }
.para-excluded { opacity: .7; }
.para-header { display: flex; align-items: center; gap: 10px; padding: 12px 16px 12px 0; cursor: pointer; }
.para-header:hover { background: rgba(60, 60, 67, 0.04); }
.para-bar { flex: none; width: 4px; align-self: stretch; border-radius: 0 2px 2px 0; margin-right: 6px; }
.para-idx { font-size: 11px; font-weight: 600; color: var(--label-secondary); letter-spacing: .6px; text-transform: uppercase; }
.para-prob { font-size: 13px; }
.chev { color: var(--label-tertiary); font-size: 20px; line-height: 1; transition: transform .2s; } .chev.open { transform: rotate(90deg); }
.para-preview { padding: 0 16px 12px 20px; font-size: 14px; color: var(--label-secondary); line-height: 1.6; cursor: pointer; }
.para-body { padding: 12px 16px 14px; border-top: 1px solid var(--label-quaternary); }
.para-text { font-size: 15px; line-height: 1.75; }
.para-excluded-text { font-size: 14px; line-height: 1.6; color: var(--label-secondary); }
.para-actions { display: flex; gap: 10px; margin-top: 10px; }
.excluded-badge { font-size: 12px; color: var(--label-secondary); background: rgba(120, 120, 128, 0.14); padding: 2px 10px; border-radius: 99px; }

/* 章节 */
.sec-card { margin-top: 10px; overflow: hidden; }
.sec-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; cursor: pointer; }
.sec-head:hover { background: rgba(60, 60, 67, 0.04); }
.sec-name { font-weight: 600; }
.sec-right { display: flex; align-items: center; gap: 14px; }
.sec-rate { font-size: 24px; font-variant-numeric: tabular-nums; }
.sec-body { padding: 6px 18px 12px; border-top: 1px solid var(--label-quaternary); background: rgba(60, 60, 67, 0.03); }
.sec-para { display: flex; align-items: baseline; gap: 10px; padding: 8px 0; border-bottom: 1px solid var(--label-quaternary); font-size: 13px; cursor: pointer; }
.sec-para:last-child { border-bottom: none; } .sec-para.excluded { opacity: .65; }
.sec-para-text { flex: 1; min-width: 0; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

/* 来源 */
.source-item { padding: 12px 20px; } .source-item.compact { padding: 8px 0; }
.source-line { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; font-size: 13px; }
.source-name { display: inline-flex; align-items: center; gap: 8px; font-weight: 500; }
.source-name i { width: 9px; height: 9px; border-radius: 50%; }
.meta-line { margin-top: 20px; text-align: center; font-size: 12px; color: var(--label-tertiary); }

/* 侧栏 */
.side-sticky { position: sticky; top: 72px; display: flex; flex-direction: column; gap: 14px; }
.side-title { font-weight: 600; margin-bottom: 8px; }
.side-actions { display: flex; flex-direction: column; gap: 8px; }
.side-actions .el-button { margin: 0; width: 100%; justify-content: flex-start; }
.side-note { font-size: 12px; color: var(--label-tertiary); text-align: center; }

/* 对比 */
.cmp { display: flex; flex-direction: column; gap: 12px; }
.cmp-sides { display: flex; align-items: center; justify-content: center; gap: 24px; }
.cmp-side { text-align: center; }
.cmp-side-rate { font-size: 28px; font-weight: 600; letter-spacing: -.5px; } .cmp-side-rate.ok { color: #1B7F3E; } .cmp-side-rate.bad { color: #C62A22; }
.cmp-arrow { font-size: 24px; color: rgba(60, 60, 67, 0.30); }
.cmp-stats { display: flex; gap: 8px; justify-content: center; }
:deep(.cmp-row-down) { background: rgba(52, 199, 89, 0.06); } :deep(.cmp-row-up) { background: rgba(255, 59, 48, 0.06); }
</style>
