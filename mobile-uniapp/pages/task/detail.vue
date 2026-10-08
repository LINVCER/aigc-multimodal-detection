<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { onLoad, onShareAppMessage } from '@dcloudio/uni-app'
import { getTaskDetail, retryTask, cancelTask, getTaskCompare } from '@/api/detect'
import { downloadReportPdf, createShare, listShares, revokeShare } from '@/api/report'
import { SOURCE_MAP, COLOR, paragraphRisk, aiRateColor } from '@/utils/constants'
import Skeleton from '@/components/Skeleton.vue'
import FeedbackSheet from '@/components/FeedbackSheet.vue'

/*
 * 检测报告页（重构版）
 *   顶部：滚过 hero 后出现的紧凑摘要条（标题 · AI 率 · 问助手）
 *   hero：AI 率环 + 达标 + 红黄绿分布条 + 比上次
 *   锚点 tabs：概览 / 段落 / 来源
 *   概览：先改这几段（优先级列表）· 改进建议
 *   段落：筛选 chips（全部 / 高 / 中 / 低 / 已排除）· 全部展开 · 卡片（句级高亮 · 问助手）
 *   来源：溯源分布
 *   处理中：四步进度（上传 → 解析 → 推理 → 汇总）按时间推进
 */

const feedbackOpen = ref(false)
const detail = ref(null)
const loading = ref(true)
const loadError = ref('')
const retrying = ref(false)
const cancelling = ref(false)
const downloading = ref(false)
const expandedMap = ref({})
const scrollIntoId = ref('')
const compact = ref(false)

/* 只读分享 */
const shareOpen = ref(false)
const shareDays = ref(7)
const shareWatermark = ref('')
const shareCreating = ref(false)
const shares = ref([])
const latestShare = ref(null)
async function openShare() {
  shareOpen.value = true
  latestShare.value = null
  if (!shareWatermark.value) shareWatermark.value = '仅供查阅'
  try { shares.value = (await listShares(taskId)) || [] } catch (e) { shares.value = [] }
}
async function doCreateShare() {
  shareCreating.value = true
  try {
    latestShare.value = await createShare(taskId, shareDays.value, shareWatermark.value.trim())
    shares.value = (await listShares(taskId)) || []
    uni.setClipboardData({ data: latestShare.value.url, showToast: false, success: () => uni.showToast({ title: '链接已复制', icon: 'none' }) })
  } catch (e) { /* request 已 toast */ } finally { shareCreating.value = false }
}
function copyShare(url) { uni.setClipboardData({ data: url, showToast: false, success: () => uni.showToast({ title: '已复制', icon: 'none' }) }) }
async function doRevoke(s) {
  try {
    await revokeShare(s.token)
    uni.showToast({ title: '已撤销', icon: 'none' })
    if (latestShare.value?.token === s.token) latestShare.value = null
    shares.value = (await listShares(taskId)) || []
  } catch (e) { /* toast */ }
}
const fmtTime = (s) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')
const paraFilter = ref('all')       // all | high | mid | low | excluded
const allExpanded = ref(false)
let pollTimer = null
let taskId = null
let startedAt = Date.now()

/* 复测对比 */
const compareOpen = ref(false)
const compareLoading = ref(false)
const compareData = ref(null)
const COMPARE_STATUS = { down: '降了', up: '涨了', same: '持平', added: '新增', removed: '已删' }
async function openCompare() {
  compareOpen.value = true
  if (compareData.value) return
  compareLoading.value = true
  try { compareData.value = await getTaskCompare(taskId) }
  catch (e) { compareOpen.value = false }
  finally { compareLoading.value = false }
}
const pct = (v) => (v == null ? '—' : Math.round(v * 100) + '%')

/* 首测欢迎（只弹一次） */
const assistantTipDismissed = ref(!!uni.getStorageSync('assistant_tip_shown'))
const showAssistantTip = computed(() => detail.value?.status === 'DONE' && !assistantTipDismissed.value)
function dismissAssistantTip(go) {
  assistantTipDismissed.value = true
  try { uni.setStorageSync('assistant_tip_shown', '1') } catch (e) { /* ignore */ }
  if (go) goAssistant()
}

/* ---------- 加载 / 轮询 ---------- */
async function load() {
  loadError.value = ''
  try { detail.value = await getTaskDetail(taskId) }
  catch (e) { loadError.value = e?.message || '加载失败' }
  finally { loading.value = false }
}
function ensurePolling() {
  if (pollTimer) return
  const s = detail.value?.status
  if (s !== 'PENDING' && s !== 'RUNNING') return
  pollTimer = setInterval(async () => {
    elapsed.value = Math.floor((Date.now() - startedAt) / 1000)
    await load()
    const st = detail.value?.status
    if (st === 'DONE' || st === 'FAILED') stopPoll()
  }, 3000)
}
function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
onUnmounted(stopPoll)

onShareAppMessage(() => {
  const d = detail.value
  const rate = (d?.status === 'DONE' && d?.aiRate != null) ? ` · AI 率 ${d.aiRate.toFixed(1)}%` : ''
  return { title: `AIGC 检测报告${rate}`, path: d?.id ? `/pages/task/detail?id=${d.id}` : '/pages/home/home' }
})

onLoad(async (query) => {
  taskId = Number(query.id)
  if (!taskId || Number.isNaN(taskId)) { loadError.value = '无效的任务号'; loading.value = false; return }
  await load()
  if (detail.value?.createdAt) {
    const t = Date.parse(String(detail.value.createdAt).replace(' ', 'T'))
    if (!Number.isNaN(t)) startedAt = t
  }
  ensurePolling()
})

/* 处理中：四步按时间推进（纯展示） */
const elapsed = ref(0)
const STEPS = ['上传完成', '解析段落', '模型推理', '汇总报告']
const stepIndex = computed(() => (elapsed.value < 3 ? 1 : elapsed.value < 10 ? 2 : 3))

/* ---------- 操作 ---------- */
async function onRetry() {
  retrying.value = true
  try {
    await retryTask(taskId)
    uni.showToast({ title: '已重新提交', icon: 'success' })
    startedAt = Date.now()
    await load()
    ensurePolling()
  } catch (e) { uni.showToast({ title: e?.message || '重试失败', icon: 'none' }) }
  finally { retrying.value = false }
}
async function onCancel() {
  const ok = await new Promise((resolve) => uni.showModal({
    title: '取消检测', content: '确定取消本次检测？取消后可在列表重新提交。',
    confirmColor: '#FF3B30', success: (r) => resolve(r.confirm), fail: () => resolve(false),
  }))
  if (!ok) return
  cancelling.value = true
  try { await cancelTask(taskId); uni.showToast({ title: '已取消', icon: 'success' }); stopPoll(); await load() }
  finally { cancelling.value = false }
}
async function onDownload() {
  if (downloading.value) return
  downloading.value = true
  try { await downloadReportPdf(taskId, detail.value?.paperTitle) }
  finally { downloading.value = false }
}
function copyCred() {
  if (!detail.value?.reportNo) return
  uni.setClipboardData({ data: `知源检测报告 编号 ${detail.value.reportNo} 验证码 ${detail.value.verifyCode}，验证：知源「验证报告」`, showToast: false, success: () => uni.showToast({ title: '凭证已复制', icon: 'none' }) })
}

function goAssistant(paragraphIdx) {
  let url = `/pages/assistant/chat?taskId=${taskId}`
  if (paragraphIdx !== undefined && paragraphIdx !== null) url += `&paragraphIdx=${paragraphIdx}`
  uni.navigateTo({ url })
}
function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/index/index' })
}
function onScroll(e) { compact.value = e.detail.scrollTop > 360 }
function goSection(id) { scrollIntoId.value = ''; setTimeout(() => { scrollIntoId.value = id }, 20) }

/* ---------- 派生 ---------- */
const pass = computed(() => { const d = detail.value; return d && d.aiRate != null && d.aiRate <= d.threshold })
const summaryColor = computed(() => aiRateColor(detail.value?.aiRate, detail.value?.threshold))
const ringCircumference = 2 * Math.PI * 86
const ringOffset = computed(() => {
  const d = detail.value
  if (!d || d.aiRate == null) return ringCircumference
  return ringCircumference * (1 - Math.min(100, Math.max(0, d.aiRate)) / 100)
})
const ringThresholdOffset = computed(() => {
  const d = detail.value
  if (!d || d.threshold == null) return ringCircumference
  return ringCircumference * (1 - Math.min(100, Math.max(0, d.threshold)) / 100)
})
const sortedSources = computed(() => {
  if (!detail.value?.sourceLabels) return []
  return Object.entries(detail.value.sourceLabels).sort((a, b) => b[1] - a[1]).map(([label, ratio]) => ({ label, ratio }))
})
const bodyParas = computed(() => (detail.value?.paragraphs || []).filter((p) => !p.excluded))
const bodyStats = computed(() => {
  const all = detail.value?.paragraphs || []
  if (!all.length) return null
  const body = bodyParas.value.length
  return { body, excluded: all.length - body }
})
/** 红 / 黄 / 绿 段数与占比，供分布条与筛选 chips */
const dist = computed(() => {
  const ps = bodyParas.value
  const high = ps.filter((p) => (p.calibratedProb || 0) >= 0.7).length
  const mid = ps.filter((p) => { const v = p.calibratedProb || 0; return v >= 0.4 && v < 0.7 }).length
  const low = ps.length - high - mid
  const n = Math.max(1, ps.length)
  return { high, mid, low, highPct: (high / n) * 100, midPct: (mid / n) * 100, lowPct: (low / n) * 100 }
})
/** 先改这几段：按概率倒序前 3 的高风险段 */
const priority = computed(() => bodyParas.value
  .filter((p) => (p.calibratedProb || 0) >= 0.5)
  .sort((a, b) => (b.calibratedProb || 0) - (a.calibratedProb || 0))
  .slice(0, 3))
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
  { key: 'all', label: '全部', n: (detail.value?.paragraphs || []).length },
  { key: 'high', label: '高', n: dist.value.high, cls: 'high' },
  { key: 'mid', label: '中', n: dist.value.mid, cls: 'mid' },
  { key: 'low', label: '低', n: dist.value.low, cls: 'low' },
  { key: 'excluded', label: '已排除', n: bodyStats.value?.excluded || 0 },
])
const EXCLUDE_REASON_LABEL = { reference: '参考文献', acknowledgement: '致谢', appendix: '附录', sectionTitle: '章节标题', caption: '图表标题' }

const suggestions = computed(() => {
  const d = detail.value
  if (!d || d.status !== 'DONE' || d.aiRate == null) return []
  const out = []
  if (d.aiRate > d.threshold) {
    out.push({ title: `AI 率超线 ${(d.aiRate - d.threshold).toFixed(1)} 个百分点`, body: `${d.aiRate.toFixed(1)}% 超过 ${d.threshold}% 红线。优先处理下面「先改这几段」，用自己的话重写核心观点，补具体数据和真实经历。`, severity: 'danger' })
  } else if (d.aiRate > d.threshold * 0.7) {
    out.push({ title: '接近红线，仍有修改空间', body: `AI 率 ${d.aiRate.toFixed(1)}%，距 ${d.threshold}% 红线不足 ${(d.threshold - d.aiRate).toFixed(1)} 个百分点。对标黄段落做小幅改写，留出安全缓冲。`, severity: 'warn' })
  } else {
    out.push({ title: '整体达标', body: `AI 率 ${d.aiRate.toFixed(1)}%，明显低于 ${d.threshold}% 红线。继续保持原创性写作。`, severity: 'success' })
  }
  if (d.sourceLabels) {
    const entries = Object.entries(d.sourceLabels).filter(([k]) => k !== 'human').sort((a, b) => b[1] - a[1])
    if (entries.length && entries[0][1] >= 0.4) {
      const src = SOURCE_MAP[entries[0][0]]?.label || entries[0][0]
      out.push({ title: `疑似大量使用 ${src}`, body: `${(entries[0][1] * 100).toFixed(0)}% 段落被判为 ${src} 风格。避免连续段落使用同一 AI 助手，改写时调整句式节奏。`, severity: 'info' })
    }
  }
  if (bodyStats.value && bodyStats.value.excluded > bodyStats.value.body) {
    out.push({ title: '识别到大量非正文段落', body: `${bodyStats.value.excluded} 段被识别为参考文献 / 图表 / 章节标题，未参与计算。若不符合预期请检查论文格式。`, severity: 'info' })
  }
  return out
})
const SEV = {
  danger: { fg: '#C62A22', bg: 'rgba(255,59,48,0.10)', dot: '#FF3B30' },
  warn: { fg: '#B26200', bg: 'rgba(255,149,0,0.12)', dot: '#FF9500' },
  success: { fg: '#1B7F3E', bg: 'rgba(52,199,89,0.10)', dot: '#34C759' },
  info: { fg: '#0056B3', bg: 'rgba(0,122,255,0.08)', dot: '#007AFF' },
}

function jumpTo(idx) {
  paraFilter.value = 'all'
  expandedMap.value[idx] = true
  setTimeout(() => { scrollIntoId.value = ''; setTimeout(() => { scrollIntoId.value = 'para-' + idx }, 20) }, 30)
}
function toggleExpand(idx) { expandedMap.value[idx] = !expandedMap.value[idx] }
function toggleAll() {
  allExpanded.value = !allExpanded.value
  const m = {}
  for (const p of (detail.value?.paragraphs || [])) m[p.paragraphIdx] = allExpanded.value
  expandedMap.value = m
}
function copyPara(text) { uni.setClipboardData({ data: text, showToast: false, success: () => uni.showToast({ title: '已复制', icon: 'none' }) }) }
</script>

<template>
  <Skeleton v-if="loading" :rows="4" />

  <view v-else-if="loadError && !detail" class="error-page">
    <view class="error-mark" />
    <text class="error-title">{{ loadError }}</text>
    <text class="error-sub">请检查任务是否已被删除或稍后重试</text>
    <view class="error-actions">
      <button class="btn-primary" @click="load">重新加载</button>
      <button class="btn-tinted" @click="goBack">返回列表</button>
    </view>
  </view>

  <template v-else-if="detail">
    <!-- 紧凑摘要条：滚过 hero 后出现 -->
    <view v-if="detail.status === 'DONE'" class="compact" :class="{ show: compact }">
      <text class="compact-title">{{ detail.paperTitle }}</text>
      <text class="compact-rate" :style="{ color: summaryColor }">{{ detail.aiRate?.toFixed(1) }}%</text>
      <text class="compact-badge" :class="pass ? 'ok' : 'bad'">{{ pass ? '达标' : '超线' }}</text>
      <text class="compact-btn" @click="goAssistant()">问助手</text>
    </view>

    <scroll-view scroll-y class="page" :scroll-into-view="scrollIntoId" :scroll-with-animation="true" @scroll="onScroll">
      <!-- ================= 处理中 ================= -->
      <view v-if="detail.status === 'RUNNING' || detail.status === 'PENDING'" class="state-card">
        <view class="state-spinner"><view class="spinner-ring" /></view>
        <text class="state-title" style="color: #B26200">检测中</text>
        <text class="state-sub">通常 15–30 秒，页面会自动刷新</text>
        <view class="steps">
          <view v-for="(s, i) in STEPS" :key="s" class="step" :class="{ done: i < stepIndex, now: i === stepIndex }">
            <view class="step-dot" /><text class="step-text">{{ s }}</text>
          </view>
        </view>
        <text class="state-paper">{{ detail.paperTitle }}</text>
        <button class="btn-tinted cancel-btn" :loading="cancelling" :disabled="cancelling" @click="onCancel">取消检测</button>
      </view>

      <!-- ================= 失败 ================= -->
      <view v-else-if="detail.status === 'FAILED'" class="state-card">
        <view class="state-mark danger"><view class="mark-x-1" /><view class="mark-x-2" /></view>
        <text class="state-title" style="color: #C62A22">检测失败</text>
        <text class="state-sub">推理服务暂时不可用，或文件无法解析出正文</text>
        <button class="btn-primary retry-btn" :loading="retrying" :disabled="retrying" @click="onRetry">重新检测</button>
      </view>

      <!-- ================= 完成 ================= -->
      <template v-else>
        <!-- hero -->
        <view id="sec-overview" class="hero-card">
          <view class="ring-wrap">
            <svg viewBox="0 0 200 200" class="ring-svg">
              <circle cx="100" cy="100" r="86" fill="none" stroke="rgba(120,120,128,0.16)" stroke-width="14"/>
              <circle cx="100" cy="100" r="86" fill="none" :stroke="summaryColor" stroke-width="14" stroke-linecap="round"
                :stroke-dasharray="ringCircumference" :stroke-dashoffset="ringOffset" transform="rotate(-90 100 100)"
                style="transition: stroke-dashoffset 900ms cubic-bezier(0.32, 0.72, 0, 1)"/>
              <circle cx="100" cy="100" r="86" fill="none" :stroke="pass ? '#34C759' : '#FF3B30'" stroke-width="14"
                :stroke-dasharray="`3 ${ringCircumference - 3}`" :stroke-dashoffset="ringThresholdOffset" transform="rotate(-90 100 100)" opacity="0.9"/>
            </svg>
            <view class="ring-center">
              <text class="ring-label">整体 AI 率</text>
              <text class="ring-rate" :style="{ color: summaryColor }">{{ detail.aiRate?.toFixed(1) }}<text class="ring-unit">%</text></text>
              <text class="ring-cap">红线 ≤ {{ detail.threshold }}%</text>
            </view>
          </view>
          <view class="verdict-pill" :class="pass ? 'ok' : 'bad'">
            <text>{{ pass ? '✓ 低于红线，达标' : '超过红线 ' + (detail.aiRate - detail.threshold).toFixed(1) + ' 个百分点' }}</text>
          </view>

          <!-- 红黄绿分布条 -->
          <view v-if="bodyStats" class="dist">
            <view class="dist-bar">
              <view class="dist-seg high" :style="{ width: dist.highPct + '%' }" />
              <view class="dist-seg mid" :style="{ width: dist.midPct + '%' }" />
              <view class="dist-seg low" :style="{ width: dist.lowPct + '%' }" />
            </view>
            <view class="dist-legend">
              <text class="dl high">高 {{ dist.high }}</text><text class="dl mid">中 {{ dist.mid }}</text><text class="dl low">低 {{ dist.low }}</text>
              <text class="dl muted">正文 {{ bodyStats.body }} 段<template v-if="bodyStats.excluded"> · 排除 {{ bodyStats.excluded }}</template></text>
            </view>
          </view>

          <!-- 比上次 -->
          <view v-if="detail.parentTaskId && detail.parentAiRate != null && detail.aiRate != null" class="compare" hover-class="compare--hover" @click="openCompare">
            <text class="compare-main" :class="detail.aiRate <= detail.parentAiRate ? 'down' : 'up'">
              比上次 {{ detail.aiRate <= detail.parentAiRate ? '−' : '+' }}{{ Math.abs(detail.aiRate - detail.parentAiRate).toFixed(1) }}%
            </text>
            <text class="compare-sub">上次 {{ detail.parentAiRate.toFixed(1) }}%<template v-if="detail.parentModelVersion && detail.parentModelVersion !== detail.modelVersion"> · 模型已更新，不可直接比较</template></text>
            <text class="compare-link">逐段对比 ›</text>
          </view>

          <text class="hero-paper">{{ detail.paperTitle }}</text>

          <view v-if="showAssistantTip" class="assist-tip">
            <image class="assist-tip-avatar" src="/static/xiaobai.gif" mode="aspectFill" />
            <view class="assist-tip-body" @click="dismissAssistantTip(true)">
              <text class="assist-tip-text">{{ pass ? '达标了。要不要我说说哪几段还是偏「机器」，下次写得更稳？' : '别急，超标不等于作弊。要我带你看哪几段贡献最大、先改哪段吗？' }}</text>
              <text class="assist-tip-cta">和助手聊聊 ›</text>
            </view>
            <text class="assist-tip-close" @click.stop="dismissAssistantTip(false)">✕</text>
          </view>

          <view v-if="detail.reportNo" class="cred" @click="copyCred">
            <view class="cred-main"><text class="cred-k">报告编号 </text><text class="cred-v">{{ detail.reportNo }}</text><text class="cred-k"> · 验证码 </text><text class="cred-v">{{ detail.verifyCode }}</text></view>
            <text class="cred-act">复制</text>
          </view>
          <view class="report-actions">
            <button class="btn-tinted" @click="goAssistant()">问助手</button>
            <button class="btn-tinted" :loading="downloading" :disabled="downloading" @click="onDownload">下载 PDF</button>
            <button class="btn-tinted" @click="openShare">只读链接</button>
          </view>
        </view>

        <!-- 锚点 tabs -->
        <view class="tabs">
          <view class="tab" hover-class="tab--hover" @click="goSection('sec-overview')"><text>概览</text></view>
          <view class="tab" hover-class="tab--hover" @click="goSection('sec-paras')"><text>段落 {{ (detail.paragraphs || []).length }}</text></view>
          <view class="tab" hover-class="tab--hover" @click="goSection('sec-sources')"><text>来源</text></view>
        </view>

        <!-- 先改这几段 -->
        <view v-if="priority.length" class="section">
          <view class="section-head-line"><text class="section-header no-pad">先改这几段</text><text class="section-sub">按贡献排序</text></view>
          <view class="prio">
            <view v-for="(p, i) in priority" :key="p.paragraphIdx" class="prio-item" hover-class="prio-item--hover" @click="jumpTo(p.paragraphIdx)">
              <view class="prio-rank" :style="{ background: paragraphRisk(p.calibratedProb || 0).color }"><text>{{ i + 1 }}</text></view>
              <view class="prio-main">
                <view class="prio-line">
                  <text class="prio-idx">段 {{ p.paragraphIdx + 1 }}</text>
                  <text class="prio-rate" :style="{ color: paragraphRisk(p.calibratedProb || 0).color }">{{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%</text>
                  <text v-if="p.sourceLabel && p.sourceLabel !== 'human'" class="prio-src">疑似 {{ SOURCE_MAP[p.sourceLabel]?.label || p.sourceLabel }}</text>
                </view>
                <text class="prio-preview">{{ (p.text || '').slice(0, 56) }}…</text>
              </view>
              <text class="prio-ask" @click.stop="goAssistant(p.paragraphIdx)">为什么</text>
            </view>
          </view>
        </view>

        <!-- 改进建议 -->
        <view v-if="suggestions.length" class="section">
          <text class="section-header">改进建议</text>
          <view class="suggest-list">
            <view v-for="(s, i) in suggestions" :key="i" class="sug-card" :style="{ background: SEV[s.severity].bg }">
              <view class="sug-dot" :style="{ background: SEV[s.severity].dot }" />
              <view class="sug-body">
                <text class="sug-title" :style="{ color: SEV[s.severity].fg }">{{ s.title }}</text>
                <text class="sug-text">{{ s.body }}</text>
              </view>
            </view>
          </view>
        </view>

        <!-- 段落 -->
        <view id="sec-paras" class="section">
          <view class="section-head-line">
            <text class="section-header no-pad">段落分析</text>
            <text class="section-link" @click="toggleAll">{{ allExpanded ? '全部收起' : '全部展开' }}</text>
          </view>
          <scroll-view class="filters" scroll-x :show-scrollbar="false">
            <view class="filters-inner">
              <view v-for="f in FILTERS" :key="f.key" class="filter" :class="[{ active: paraFilter === f.key }, f.cls]" hover-class="filter--hover" @click="paraFilter = f.key">
                <text>{{ f.label }}</text><text class="filter-n">{{ f.n }}</text>
              </view>
            </view>
          </scroll-view>

          <view v-if="!filteredParas.length" class="empty-paras"><text>这一类没有段落</text></view>
          <view
            v-for="p in filteredParas" :key="p.paragraphIdx" :id="'para-' + p.paragraphIdx"
            class="para-card" :class="{ 'para-excluded': p.excluded }"
          >
            <view class="para-header" hover-class="para-header-hover" @click="toggleExpand(p.paragraphIdx)">
              <view class="para-bar" :style="{ background: p.excluded ? 'rgba(120,120,128,0.3)' : paragraphRisk(p.calibratedProb || 0).color }" />
              <view class="para-header-left">
                <text class="para-idx">段 {{ p.paragraphIdx + 1 }}</text>
                <text v-if="p.excluded" class="excluded-badge">已排除 · {{ EXCLUDE_REASON_LABEL[p.excludeReason] || '非正文' }}</text>
                <text v-else class="para-prob" :style="{ color: paragraphRisk(p.calibratedProb || 0).color }">
                  {{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%
                  <text v-if="p.sourceLabel && p.sourceLabel !== 'human'" class="para-src">· 疑似 {{ SOURCE_MAP[p.sourceLabel]?.label || p.sourceLabel }}</text>
                </text>
                <text v-if="p.sectionName" class="para-sec">{{ p.sectionName }}</text>
              </view>
              <text class="chevron" :class="{ expanded: expandedMap[p.paragraphIdx] }">›</text>
            </view>

            <view v-if="!expandedMap[p.paragraphIdx]" class="para-preview" @click="toggleExpand(p.paragraphIdx)">
              {{ (p.text || '').slice(0, 72) }}{{ (p.text || '').length > 72 ? '…' : '' }}
            </view>

            <view v-if="expandedMap[p.paragraphIdx]" class="para-body">
              <view v-if="p.excluded" class="para-excluded-text">{{ p.text }}</view>
              <view v-else class="para-text">
                <text v-for="s in p.sentences" :key="s.sentenceIdx" :style="{ background: paragraphRisk(s.aiProb).bg }">{{ s.text }}</text>
              </view>
              <view class="para-actions">
                <text class="pa" @click="copyPara(p.text)">复制</text>
                <text v-if="!p.excluded && (p.calibratedProb || 0) >= 0.4" class="pa primary" @click="goAssistant(p.paragraphIdx)">为什么像 AI？</text>
              </view>
            </view>
          </view>
          <view class="legend-row"><view class="sw high" /><text>高 ≥70%</text><view class="sw mid" /><text>中 40–70%</text><text class="legend-note">句子按概率着色</text></view>
        </view>

        <!-- 来源 -->
        <view id="sec-sources" class="section">
          <text class="section-header">疑似来源分布</text>
          <view class="group-card">
            <view v-for="(s, i) in sortedSources" :key="s.label" class="source-item">
              <view class="source-line">
                <view class="source-name-wrap">
                  <view class="source-dot" :style="{ background: SOURCE_MAP[s.label]?.color || COLOR.systemGray }" />
                  <text class="source-name">{{ SOURCE_MAP[s.label]?.label || s.label }}</text>
                </view>
                <text class="source-ratio">{{ (s.ratio * 100).toFixed(0) }}%</text>
              </view>
              <view class="bar-track"><view class="bar-fill" :style="{ width: (s.ratio * 100) + '%', background: SOURCE_MAP[s.label]?.color || COLOR.systemGray }" /></view>
              <view v-if="i < sortedSources.length - 1" class="row-sep" />
            </view>
            <view v-if="!sortedSources.length" class="empty-paras"><text>暂无溯源数据</text></view>
          </view>
        </view>

        <!-- 申诉 -->
        <view class="appeal-card" hover-class="appeal-card-hover" @click="feedbackOpen = true">
          <view class="appeal-icon"><view class="appeal-flag-mast" /><view class="appeal-flag-cloth" /></view>
          <view class="appeal-body">
            <text class="appeal-title">对本次结果有疑问？</text>
            <text class="appeal-sub">勾选判错的段落提交申诉，人工复核后回复</text>
          </view>
          <text class="appeal-chevron">›</text>
        </view>
        <view class="meta-line"><text>模型 {{ detail.modelVersion || '—' }} · {{ detail.createdAt }} · 置信度仅供参考，建议人工复核</text></view>
      </template>
    </scroll-view>
  </template>

  <FeedbackSheet v-model="feedbackOpen" :task-id="Number(taskId) || 0" default-category="appeal" :paragraphs="detail?.paragraphs || []" />

  <!-- 只读分享 sheet -->
  <view v-if="shareOpen" class="cmp-mask" @click="shareOpen = false">
    <view class="cmp-sheet" @click.stop>
      <view class="cmp-handle" />
      <view class="cmp-head"><text class="cmp-title">分享只读报告</text><text class="cmp-close" @click="shareOpen = false">✕</text></view>
      <view class="share-row">
        <text class="share-label">有效期</text>
        <view class="share-chips">
          <text v-for="d in [1, 7, 30]" :key="d" class="share-chip" :class="{ on: shareDays === d }" @click="shareDays = d">{{ d }} 天</text>
        </view>
      </view>
      <view class="share-row">
        <text class="share-label">水印</text>
        <input v-model="shareWatermark" class="share-input" maxlength="40" placeholder="如：仅供张老师审阅" placeholder-style="color: rgba(60,60,67,0.30)" />
      </view>
      <text class="share-hint">对方只能看报告，不能申诉、下载或问助手；页面带水印，随时可撤销。</text>
      <button class="share-submit" :loading="shareCreating" :disabled="shareCreating" @click="doCreateShare">生成链接并复制</button>
      <view v-if="latestShare" class="share-result" @click="copyShare(latestShare.url)">
        <text class="share-url">{{ latestShare.url }}</text>
        <text class="share-copy">复制</text>
      </view>
      <scroll-view v-if="shares.length" scroll-y class="share-list">
        <text class="share-sub">已生成的链接</text>
        <view v-for="s in shares" :key="s.token" class="share-item" :class="{ dead: s.revoked || s.expired }">
          <view class="share-item-main">
            <text class="share-item-token">…{{ s.token.slice(-8) }}</text>
            <text class="share-item-meta">{{ s.watermark || '默认水印' }} · 至 {{ fmtTime(s.expiresAt) }} · 看过 {{ s.viewCount }} 次</text>
          </view>
          <text v-if="s.revoked" class="share-item-tag">已撤销</text>
          <text v-else-if="s.expired" class="share-item-tag">已过期</text>
          <template v-else>
            <text class="share-item-act" @click="copyShare(s.url)">复制</text>
            <text class="share-item-act danger" @click="doRevoke(s)">撤销</text>
          </template>
        </view>
      </scroll-view>
    </view>
  </view>

  <!-- 复测对比 sheet -->
  <view v-if="compareOpen" class="cmp-mask" @click="compareOpen = false">
    <view class="cmp-sheet" @click.stop>
      <view class="cmp-handle" />
      <view class="cmp-head"><text class="cmp-title">与上次检测对比</text><text class="cmp-close" @click="compareOpen = false">✕</text></view>
      <view v-if="compareLoading" class="cmp-loading"><text>加载中…</text></view>
      <template v-else-if="compareData">
        <text class="cmp-headline" :class="compareData.comparable ? (compareData.summary.pass ? 'ok' : 'warn') : ''">{{ compareData.summary.headline }}</text>
        <view class="cmp-sides">
          <view class="cmp-side"><text class="cmp-side-label">上次</text><text class="cmp-side-rate">{{ compareData.parent.aiRate == null ? '—' : compareData.parent.aiRate.toFixed(1) + '%' }}</text></view>
          <text class="cmp-arrow">→</text>
          <view class="cmp-side"><text class="cmp-side-label">本次</text><text class="cmp-side-rate" :class="compareData.summary.pass ? 'ok' : 'bad'">{{ compareData.current.aiRate == null ? '—' : compareData.current.aiRate.toFixed(1) + '%' }}</text></view>
        </view>
        <view class="cmp-stats">
          <text class="cmp-stat down">降 {{ compareData.summary.down }}</text>
          <text class="cmp-stat up">涨 {{ compareData.summary.up }}</text>
          <text class="cmp-stat added">新增 {{ compareData.summary.added }}</text>
          <text class="cmp-stat removed">删除 {{ compareData.summary.removed }}</text>
        </view>
        <scroll-view scroll-y class="cmp-list">
          <view v-for="(r, i) in compareData.rows" :key="i" class="cmp-row" :class="r.status">
            <view class="cmp-row-head">
              <text class="cmp-row-idx"><template v-if="r.currIdx != null">本 {{ r.currIdx + 1 }}</template><template v-if="r.currIdx != null && r.parentIdx != null"> ← </template><template v-if="r.parentIdx != null">上 {{ r.parentIdx + 1 }}</template></text>
              <text class="cmp-row-status" :class="r.status">{{ COMPARE_STATUS[r.status] }}<template v-if="r.delta != null"> {{ r.delta > 0 ? '+' : '' }}{{ Math.round(r.delta * 100) }}pp</template></text>
            </view>
            <text class="cmp-row-preview">{{ r.preview }}…</text>
            <text class="cmp-row-probs">{{ pct(r.parentProb) }} → {{ pct(r.currProb) }}</text>
          </view>
        </scroll-view>
        <text class="cmp-foot">段落按文本相似度配对；改动很大的段会分别算作「新增」和「删除」。</text>
      </template>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page { height: 100vh; padding: $sp-3 $sp-4 120rpx; box-sizing: border-box; background: $bg-grouped-primary; }

/* 紧凑摘要条 */
.compact {
  position: fixed; left: 0; right: 0; top: 0; z-index: $z-navbar;
  display: flex; align-items: center; gap: $sp-2;
  padding: $sp-2 $sp-4; padding-top: #{"calc(#{$sp-2} + env(safe-area-inset-top))"};
  @include backdrop-blur($blur-material, rgba(255, 255, 255, 0.86));
  border-bottom: $stroke-hairline solid $separator;
  transform: translateY(-110%); transition: transform .22s $ease-standard;
  &.show { transform: translateY(0); }
}
.compact-title { flex: 1; min-width: 0; font-size: $fs-footnote; font-weight: $fw-medium; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.compact-rate { flex: none; font-size: $fs-headline; font-weight: $fw-bold; font-variant-numeric: tabular-nums; }
.compact-badge { flex: none; font-size: $fs-caption-2; font-weight: $fw-semibold; padding: 2rpx $sp-2; border-radius: $radius-pill; &.ok { background: $success-bg; color: $success-fg; } &.bad { background: $danger-bg; color: $danger-fg; } }
.compact-btn { flex: none; font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-semibold; }

/* 错误 */
.error-page { min-height: 100vh; padding: 200rpx $sp-6; display: flex; flex-direction: column; align-items: center; background: $bg-grouped-primary; }
.error-mark { width: 96rpx; height: 96rpx; border-radius: 50%; background: $danger-bg; position: relative; margin-bottom: $sp-5; &::before { content: '!'; position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 56rpx; font-weight: $fw-bold; color: $danger-solid; } }
.error-title { font-size: $fs-title-3; font-weight: $fw-semibold; color: $label-primary; }
.error-sub { font-size: $fs-subhead; color: $label-secondary; margin-top: $sp-2; text-align: center; }
.error-actions { display: flex; gap: $sp-3; margin-top: $sp-8; width: 100%; justify-content: center; }

/* 状态卡 */
.state-card { @include card; padding: 80rpx $sp-5 60rpx; text-align: center; display: flex; flex-direction: column; align-items: center; }
.state-title { display: block; font-size: $fs-title-3; font-weight: $fw-semibold; margin-top: $sp-4; }
.state-sub { display: block; font-size: $fs-subhead; color: $label-secondary; margin-top: $sp-2; }
.state-paper { display: block; font-size: $fs-footnote; color: $label-secondary; margin-top: $sp-3; }
.state-spinner { width: 96rpx; height: 96rpx; }
.spinner-ring { width: 100%; height: 100%; border-radius: 50%; border: 8rpx solid rgba(255, 149, 0, 0.18); border-top-color: $warning-solid; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.steps { display: flex; justify-content: space-between; width: 100%; margin-top: $sp-5; padding: 0 $sp-2; }
.step { display: flex; flex-direction: column; align-items: center; gap: 8rpx; flex: 1; }
.step-dot { width: 20rpx; height: 20rpx; border-radius: 50%; background: $fill-primary; }
.step-text { font-size: $fs-caption-2; color: $label-tertiary; }
.step.done .step-dot { background: $success-solid; } .step.done .step-text { color: $label-secondary; }
.step.now .step-dot { background: $warning-solid; box-shadow: 0 0 0 8rpx rgba(255, 149, 0, 0.18); } .step.now .step-text { color: $warning-fg; font-weight: $fw-semibold; }
.state-mark { width: 96rpx; height: 96rpx; border-radius: 50%; position: relative; &.danger { background: $danger-bg; } }
.mark-x-1, .mark-x-2 { position: absolute; left: 20%; right: 20%; top: 48%; height: 6rpx; border-radius: 3rpx; background: $danger-solid; }
.mark-x-1 { transform: rotate(45deg); } .mark-x-2 { transform: rotate(-45deg); }
.retry-btn, .cancel-btn { margin-top: $sp-5; min-width: 320rpx; }

/* 按钮 */
.btn-primary { min-width: 240rpx; height: $size-btn-h-lg; line-height: $size-btn-h-lg; background: $brand-primary; color: #fff; font-size: $fs-headline; font-weight: $fw-semibold; border-radius: $radius-pill; &::after { border: none; } &[disabled] { opacity: 0.5; } }
.btn-tinted { flex: 1; margin: 0; min-width: 0; height: 80rpx; line-height: 80rpx; background: $brand-primary-wash; color: $brand-primary; font-size: $fs-subhead; font-weight: $fw-semibold; border-radius: $radius-pill; &::after { border: none; } }

/* hero */
.hero-card { @include card; padding: $sp-5 $sp-4 $sp-4; text-align: center; display: flex; flex-direction: column; align-items: center; }
.ring-wrap { position: relative; width: 400rpx; height: 400rpx; margin: 0 auto $sp-2; }
.ring-svg { width: 400rpx; height: 400rpx; display: block; }
.ring-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.ring-label { font-size: $fs-caption-2; color: $label-secondary; text-transform: uppercase; letter-spacing: $tracking-wide; margin-bottom: 4rpx; }
.ring-rate { font-size: 96rpx; font-weight: $fw-bold; letter-spacing: -2rpx; line-height: 1; font-variant-numeric: tabular-nums; }
.ring-unit { font-size: 36rpx; font-weight: $fw-semibold; color: $label-secondary; margin-left: 4rpx; }
.ring-cap { font-size: $fs-caption-1; color: $label-secondary; margin-top: $sp-1; }
.verdict-pill { display: inline-flex; padding: $sp-2 $sp-4; border-radius: $radius-pill; font-size: $fs-subhead; font-weight: $fw-semibold; &.ok { background: $success-bg; color: $success-fg; } &.bad { background: $danger-bg; color: $danger-fg; } }
.dist { width: 100%; margin-top: $sp-4; }
.dist-bar { display: flex; height: 16rpx; border-radius: $radius-pill; overflow: hidden; background: $fill-quaternary; }
.dist-seg { height: 100%; &.high { background: $danger-solid; } &.mid { background: $warning-solid; } &.low { background: $success-solid; } }
.dist-legend { display: flex; gap: $sp-3; margin-top: $sp-2; font-size: $fs-caption-1; }
.dl { font-weight: $fw-semibold; &.high { color: $danger-fg; } &.mid { color: $warning-fg; } &.low { color: $success-fg; } &.muted { margin-left: auto; color: $label-secondary; font-weight: $fw-regular; } }
.compare { width: 100%; margin-top: $sp-3; padding: $sp-2 $sp-3; border-radius: $radius-md; background: $fill-quaternary; display: flex; align-items: center; gap: $sp-2; &--hover { opacity: 0.7; } }
.compare-main { font-size: $fs-subhead; font-weight: $fw-semibold; &.down { color: $success-fg; } &.up { color: $danger-fg; } }
.compare-sub { flex: 1; font-size: $fs-caption-2; color: $label-secondary; text-align: left; }
.compare-link { font-size: $fs-caption-1; color: $brand-primary; font-weight: $fw-medium; }
.hero-paper { display: block; width: 100%; font-size: $fs-footnote; color: $label-secondary; margin-top: $sp-3; padding-top: $sp-3; border-top: $stroke-hairline solid $separator; }
.assist-tip { width: 100%; display: flex; align-items: flex-start; gap: $sp-2; margin-top: $sp-3; padding: $sp-3; border-radius: $radius-md; background: $brand-primary-wash; text-align: left; }
.assist-tip-avatar { flex: none; width: 48rpx; height: 48rpx; border-radius: $radius-pill; background: $brand-gradient-vivid; color: #fff; font-size: $fs-caption-2; font-weight: $fw-bold; display: flex; align-items: center; justify-content: center; }
.assist-tip-body { flex: 1; }
.assist-tip-text { display: block; font-size: $fs-footnote; color: $label-primary; line-height: $lh-normal; }
.assist-tip-cta { display: block; margin-top: $sp-1; font-size: $fs-footnote; font-weight: $fw-semibold; color: $brand-primary; }
.assist-tip-close { flex: none; color: $label-tertiary; font-size: $fs-footnote; padding: 0 $sp-1; }
.cred { width: 100%; margin-top: $sp-3; padding: $sp-2 $sp-3; border-radius: $radius-md; background: $success-bg; display: flex; align-items: center; gap: $sp-2; }
.cred-main { flex: 1; min-width: 0; font-size: $fs-caption-1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.cred-k { color: $label-secondary; } .cred-v { color: $success-fg; font-weight: $fw-semibold; letter-spacing: 1rpx; }
.cred-act { flex: none; font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-semibold; }
.report-actions { width: 100%; margin-top: $sp-3; display: flex; gap: $sp-2; }

/* 锚点 tabs */
.tabs { display: flex; gap: $sp-2; margin-top: $sp-3; padding: 6rpx; background: $fill-tertiary; border-radius: $radius-btn; }
.tab { flex: 1; height: 64rpx; display: flex; align-items: center; justify-content: center; border-radius: 14rpx; font-size: $fs-footnote; font-weight: $fw-medium; color: $label-primary; &--hover { background: $bg-primary; } }

/* section */
.section { margin-top: $sp-6; }
.section-header { display: block; padding: 0 $sp-3 $sp-2; font-size: $fs-footnote; font-weight: $fw-medium; color: $label-secondary; text-transform: uppercase; letter-spacing: $tracking-wide; &.no-pad { padding-left: 0; } }
.section-head-line { display: flex; justify-content: space-between; align-items: baseline; padding: 0 $sp-3 $sp-2; }
.section-sub { font-size: $fs-caption-2; color: $label-tertiary; }
.section-link { font-size: $fs-caption-1; color: $brand-primary; font-weight: $fw-medium; }
.group-card { @include card-flush; }
.empty-paras { padding: $sp-6 0; text-align: center; font-size: $fs-footnote; color: $label-tertiary; }

/* 先改这几段 */
.prio { @include card-flush; }
.prio-item { display: flex; align-items: center; gap: $sp-3; padding: $sp-3 $sp-4; border-bottom: $stroke-hairline solid $separator; &:last-child { border-bottom: none; } &--hover { background: $fill-quaternary; } }
.prio-rank { flex: none; width: 48rpx; height: 48rpx; border-radius: $radius-pill; color: #fff; font-size: $fs-footnote; font-weight: $fw-bold; display: flex; align-items: center; justify-content: center; }
.prio-main { flex: 1; min-width: 0; }
.prio-line { display: flex; align-items: baseline; gap: $sp-2; }
.prio-idx { font-size: $fs-caption-1; color: $label-secondary; font-weight: $fw-semibold; }
.prio-rate { font-size: $fs-subhead; font-weight: $fw-bold; font-variant-numeric: tabular-nums; }
.prio-src { font-size: $fs-caption-2; color: $label-secondary; }
.prio-preview { display: block; font-size: $fs-footnote; color: $label-primary; margin-top: 2rpx; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.prio-ask { flex: none; font-size: $fs-caption-1; color: $brand-primary; font-weight: $fw-semibold; padding: 6rpx $sp-2; border-radius: $radius-pill; background: $brand-primary-wash; }

/* 建议 */
.suggest-list { display: flex; flex-direction: column; gap: $sp-2; }
.sug-card { border-radius: $radius-lg; padding: $sp-3 $sp-3 $sp-3 $sp-2; display: flex; gap: $sp-3; align-items: flex-start; }
.sug-dot { width: 12rpx; height: 12rpx; border-radius: 50%; margin-top: 14rpx; flex-shrink: 0; }
.sug-body { flex: 1; }
.sug-title { display: block; font-size: $fs-headline; font-weight: $fw-semibold; margin-bottom: 6rpx; }
.sug-text { display: block; font-size: $fs-subhead; color: $label-primary; opacity: 0.85; line-height: $lh-normal; }

/* 筛选 */
.filters { white-space: nowrap; margin: 0 0 $sp-2; }
.filters-inner { display: inline-flex; gap: $sp-2; padding: 0 $sp-1 4rpx; }
.filter { display: inline-flex; align-items: center; gap: 6rpx; flex: none; padding: 8rpx $sp-3; border-radius: $radius-pill; background: $bg-primary; border: $stroke-hairline solid $separator; font-size: $fs-footnote; color: $label-primary; &--hover { opacity: 0.7; }
  &.active { background: $label-primary; color: #fff; border-color: $label-primary; }
  &.high.active { background: $danger-solid; border-color: $danger-solid; } &.mid.active { background: $warning-solid; border-color: $warning-solid; } &.low.active { background: $success-solid; border-color: $success-solid; } }
.filter-n { font-size: $fs-caption-2; opacity: 0.7; font-variant-numeric: tabular-nums; }
.legend-row { display: flex; align-items: center; gap: 8rpx; margin-top: $sp-2; padding: 0 $sp-2; font-size: $fs-caption-2; color: $label-secondary; }
.sw { width: 24rpx; height: 12rpx; border-radius: 4rpx; &.high { background: rgba(255, 59, 48, 0.3); } &.mid { background: rgba(255, 149, 0, 0.3); margin-left: $sp-2; } }
.legend-note { margin-left: auto; }

/* 段落卡 */
.para-card { @include card-flush; margin-bottom: $sp-2; overflow: hidden; }
.para-excluded { opacity: 0.7; }
.para-header { display: flex; justify-content: space-between; align-items: center; padding: $sp-3 $sp-4 $sp-3 0; }
.para-header-hover { background: rgba(60, 60, 67, 0.06); }
.para-bar { flex: none; width: 8rpx; align-self: stretch; margin-right: $sp-3; border-radius: 0 4rpx 4rpx 0; }
.para-header-left { display: flex; align-items: baseline; gap: $sp-2; flex: 1; min-width: 0; flex-wrap: wrap; }
.para-idx { font-size: $fs-caption-2; color: $label-secondary; font-weight: $fw-semibold; letter-spacing: 1rpx; }
.para-prob { font-size: $fs-subhead; font-weight: $fw-semibold; }
.para-src { color: $label-secondary; font-weight: $fw-regular; font-size: $fs-caption-1; }
.para-sec { font-size: $fs-caption-2; color: $label-tertiary; }
.excluded-badge { font-size: $fs-caption-2; color: $label-secondary; background: $fill-tertiary; padding: 4rpx 16rpx; border-radius: $radius-pill; }
.chevron { font-size: 40rpx; color: $label-tertiary; line-height: 1; transition: transform .2s; &.expanded { transform: rotate(90deg); } }
.para-preview { padding: 0 $sp-4 $sp-3 (8rpx + $sp-3); font-size: $fs-subhead; line-height: $lh-normal; color: $label-secondary; }
.para-body { padding: $sp-3 $sp-4 $sp-3; border-top: $stroke-hairline solid $label-quaternary; }
.para-text { font-size: $fs-body; line-height: $lh-relaxed; color: $label-primary; }
.para-excluded-text { font-size: $fs-callout; line-height: $lh-normal; color: $label-secondary; }
.para-actions { display: flex; gap: $sp-3; margin-top: $sp-3; }
.pa { font-size: $fs-footnote; color: $label-secondary; padding: 8rpx $sp-3; border-radius: $radius-pill; background: $fill-quaternary; &.primary { color: $brand-primary; background: $brand-primary-wash; font-weight: $fw-semibold; } }

/* 来源 */
.source-item { padding: $sp-4 $sp-4; position: relative; }
.source-line { display: flex; justify-content: space-between; align-items: center; margin-bottom: $sp-2; }
.source-name-wrap { display: inline-flex; align-items: center; }
.source-dot { width: 20rpx; height: 20rpx; border-radius: 50%; margin-right: $sp-2; }
.source-name { font-size: $fs-subhead; color: $label-primary; font-weight: $fw-medium; }
.source-ratio { font-size: $fs-callout; color: $label-primary; font-weight: $fw-semibold; font-variant-numeric: tabular-nums; }
.bar-track { height: 10rpx; background: $fill-tertiary; border-radius: 5rpx; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 5rpx; }
.row-sep { position: absolute; left: $sp-4; right: 0; bottom: 0; height: $stroke-hairline; background: $separator; }

/* 申诉 */
.appeal-card { margin-top: $sp-5; padding: $sp-3 $sp-4; background: $bg-primary; border-radius: $radius-lg; box-shadow: $shadow-card; display: flex; align-items: center; }
.appeal-card-hover { background: rgba(60, 60, 67, 0.05); }
.appeal-icon { position: relative; width: 48rpx; height: 48rpx; margin-right: $sp-3; flex-shrink: 0; }
.appeal-flag-mast { position: absolute; left: 12rpx; top: 4rpx; width: 4rpx; height: 40rpx; background: $label-primary; border-radius: 2rpx; }
.appeal-flag-cloth { position: absolute; left: 16rpx; top: 4rpx; width: 26rpx; height: 20rpx; background: $brand-primary; clip-path: polygon(0 0, 100% 0, 70% 50%, 100% 100%, 0 100%); }
.appeal-body { flex: 1; }
.appeal-title { display: block; font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.appeal-sub { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-top: 6rpx; }
.appeal-chevron { color: $label-tertiary; font-size: 36rpx; margin-left: $sp-2; }
.meta-line { margin-top: $sp-4; text-align: center; font-size: $fs-caption-2; color: $label-tertiary; }

/* 只读分享 sheet */
.share-row { display: flex; align-items: center; gap: $sp-3; margin-top: $sp-3; }
.share-label { flex: none; width: 96rpx; font-size: $fs-footnote; color: $label-secondary; }
.share-chips { display: flex; gap: $sp-2; }
.share-chip { padding: 10rpx $sp-3; border-radius: $radius-pill; background: $fill-tertiary; font-size: $fs-footnote; color: $label-primary; &.on { background: $brand-primary; color: #fff; font-weight: $fw-semibold; } }
.share-input { flex: 1; height: 72rpx; padding: 0 $sp-3; border-radius: $radius-md; background: $bg-grouped-primary; font-size: $fs-footnote; color: $label-primary; }
.share-hint { display: block; margin-top: $sp-3; font-size: $fs-caption-2; color: $label-tertiary; line-height: $lh-normal; }
.share-submit { margin-top: $sp-3; height: $size-btn-h-lg; line-height: $size-btn-h-lg; background: $brand-primary; color: #fff; font-size: $fs-headline; font-weight: $fw-semibold; border-radius: $radius-pill; &::after { border: none; } }
.share-result { margin-top: $sp-3; padding: $sp-2 $sp-3; border-radius: $radius-md; background: $success-bg; display: flex; align-items: center; gap: $sp-2; }
.share-url { flex: 1; min-width: 0; font-size: $fs-caption-1; color: $success-fg; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.share-copy { flex: none; font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-semibold; }
.share-list { max-height: 40vh; margin-top: $sp-3; }
.share-sub { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-bottom: $sp-1; }
.share-item { display: flex; align-items: center; gap: $sp-2; padding: $sp-2 0; border-bottom: $stroke-hairline solid $separator; &.dead { opacity: 0.55; } }
.share-item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.share-item-token { font-size: $fs-footnote; color: $label-primary; }
.share-item-meta { font-size: $fs-caption-2; color: $label-tertiary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.share-item-tag { flex: none; font-size: $fs-caption-2; color: $label-tertiary; }
.share-item-act { flex: none; font-size: $fs-footnote; color: $brand-primary; padding: 0 $sp-1; &.danger { color: $danger-fg; } }

/* 复测对比 sheet */
.cmp-mask { position: fixed; left: 0; right: 0; top: 0; bottom: 0; background: rgba(0, 0, 0, 0.35); z-index: $z-sheet; display: flex; align-items: flex-end; }
.cmp-sheet { width: 100%; max-height: 86vh; display: flex; flex-direction: column; background: $bg-primary; border-radius: $radius-sheet $radius-sheet 0 0; padding: $sp-3 $sp-4; padding-bottom: #{"calc(#{$sp-4} + env(safe-area-inset-bottom))"}; }
.cmp-handle { width: 72rpx; height: 8rpx; border-radius: $radius-pill; background: $fill-primary; margin: 0 auto $sp-3; }
.cmp-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: $sp-2; }
.cmp-title { font-size: $fs-headline; font-weight: $fw-semibold; }
.cmp-close { color: $label-tertiary; font-size: $fs-body; padding: 0 $sp-1; }
.cmp-loading { padding: $sp-8 0; text-align: center; color: $label-secondary; font-size: $fs-subhead; }
.cmp-headline { display: block; font-size: $fs-subhead; line-height: $lh-normal; padding: $sp-2 $sp-3; border-radius: $radius-md; background: $fill-quaternary; color: $label-primary; &.ok { background: $success-bg; color: $success-fg; } &.warn { background: $warning-bg; color: $warning-fg; } }
.cmp-sides { display: flex; align-items: center; justify-content: center; gap: $sp-5; margin: $sp-3 0 $sp-2; }
.cmp-side { display: flex; flex-direction: column; align-items: center; }
.cmp-side-label { font-size: $fs-caption-1; color: $label-secondary; }
.cmp-side-rate { font-size: $fs-title-1; font-weight: $fw-bold; letter-spacing: -1rpx; &.ok { color: $success-fg; } &.bad { color: $danger-fg; } }
.cmp-arrow { font-size: $fs-title-2; color: $label-quaternary; }
.cmp-stats { display: flex; justify-content: center; gap: $sp-2; margin-bottom: $sp-2; }
.cmp-stat { font-size: $fs-caption-1; font-weight: $fw-semibold; padding: 2rpx $sp-2; border-radius: $radius-xs; &.down { background: $success-bg; color: $success-fg; } &.up { background: $danger-bg; color: $danger-fg; } &.added { background: $warning-bg; color: $warning-fg; } &.removed { background: $neutral-bg; color: $neutral-fg; } }
.cmp-list { flex: 1; min-height: 0; max-height: 46vh; }
.cmp-row { padding: $sp-2 $sp-3; border-radius: $radius-md; margin-bottom: $sp-1; background: $bg-grouped-primary; &.down { background: $success-bg; } &.up { background: $danger-bg; } }
.cmp-row-head { display: flex; justify-content: space-between; align-items: center; }
.cmp-row-idx { font-size: $fs-caption-1; color: $label-secondary; }
.cmp-row-status { font-size: $fs-caption-1; font-weight: $fw-semibold; &.down { color: $success-fg; } &.up { color: $danger-fg; } &.same { color: $label-secondary; } &.added { color: $warning-fg; } &.removed { color: $neutral-fg; } }
.cmp-row-preview { display: block; font-size: $fs-footnote; color: $label-primary; margin-top: 4rpx; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.cmp-row-probs { display: block; font-size: $fs-caption-2; color: $label-secondary; margin-top: 2rpx; font-variant-numeric: tabular-nums; }
.cmp-foot { display: block; font-size: $fs-caption-2; color: $label-tertiary; margin-top: $sp-2; }
</style>
