<script setup>
import { ref, computed } from 'vue'
import { onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import { uploadPaper, detectTextDirect, listTasks } from '@/api/detect'
import { requestAndSaveSubscribe } from '@/api/wechat'
import { SCENARIO_MAP, paragraphRisk, aiRateColor } from '@/utils/constants'
import { useAuth } from '@/store/auth'
import AssistantFab from '@/components/AssistantFab.vue'

/*
 * 论文检测（tab「上传」）· 只做论文，音频 / 图像入口已移除
 *
 * 结构：大标题 + 文件 / 粘贴分段 → 场景横滑 chips → 文件投放卡 / 粘贴区 → 修改稿对比 → 最近检测 → 底部固定 CTA
 * 入口参数：首页 quick-tile 通过 storage 传 pending_upload_mode（switchTab 不能带参）
 */

// Wave 3.3 · 微信订阅消息模板 ID（占位 · 上线前替换）
const DETECT_DONE_TMPL = 'PLACEHOLDER_DETECT_DONE'
const PASTE_MAX = 5000
const FILE_MAX = 20 * 1024 * 1024

const auth = useAuth()

onShareAppMessage(() => ({ title: '论文 AI 率检测 · 段落热力 + 疑似来源分布', path: '/pages/upload/upload' }))
onShareTimeline(() => ({ title: '论文 AI 率检测' }))

const mode = ref('file')            // file | paste
const scenario = ref('academic_bachelor')
const file = ref(null)
const submitting = ref(false)
const sc = computed(() => SCENARIO_MAP[scenario.value] || SCENARIO_MAP.other)

/* 修改稿对比 */
const prevTasks = ref([])
const prevIdx = ref(-1)
const prevLabels = computed(() => ['不关联', ...prevTasks.value.map((t) => `${t.paperTitle} · ${t.aiRate == null ? '—' : t.aiRate.toFixed(1) + '%'}`)])
const parentTaskId = computed(() => (prevIdx.value >= 0 ? prevTasks.value[prevIdx.value]?.id : undefined))
const parentTask = computed(() => (prevIdx.value >= 0 ? prevTasks.value[prevIdx.value] : null))
function onPrevChange(e) { prevIdx.value = Number(e.detail.value) - 1 }

/* 最近检测：给用户一个「上次测到哪」的锚点 */
const recent = ref([])
async function loadTasks() {
  try {
    const rows = await listTasks()
    const done = (rows || []).filter((t) => t.status === 'DONE')
    prevTasks.value = done.slice(0, 20)
    recent.value = (rows || []).slice(0, 3)
  } catch (e) { prevTasks.value = []; recent.value = [] }
}

onShow(() => {
  loadTasks()
  const pendingMode = uni.getStorageSync('pending_upload_mode')
  if (pendingMode === 'paste' || pendingMode === 'file') mode.value = pendingMode
  uni.removeStorageSync('pending_upload_mode')
})

/* ---------- 文件 ---------- */
function pickFile() {
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({
    count: 1, type: 'file', extension: ['.pdf', '.doc', '.docx', '.txt'],
    success: (res) => {
      const f = res.tempFiles[0]
      if (f.size > FILE_MAX) return uni.showToast({ title: '文件不能超过 20MB', icon: 'none' })
      file.value = { path: f.path, name: f.name, size: f.size }
    },
  })
  // #endif
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf,.doc,.docx,.txt'
  input.onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > FILE_MAX) return uni.showToast({ title: '文件不能超过 20MB', icon: 'none' })
    file.value = { path: URL.createObjectURL(f), name: f.name, size: f.size }
  }
  input.click()
  // #endif
}
function clearFile() { file.value = null }
function humanBytes(n) {
  if (!n) return ''
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}
function extOf(name) { return (name || '').split('.').pop().toUpperCase().slice(0, 4) }

async function submit() {
  if (!file.value) return uni.showToast({ title: '请先选择论文文件', icon: 'none' })
  submitting.value = true
  uni.showLoading({ title: '上传中…', mask: true })
  try {
    const task = await uploadPaper(file.value.path, file.value.name, scenario.value, auth.userId, 'text', parentTaskId.value)
    uni.hideLoading()
    if (!task?.id) throw new Error('提交成功但未拿到任务号')
    requestAndSaveSubscribe([DETECT_DONE_TMPL])
    uni.showToast({ title: '已提交', icon: 'success', duration: 600 })
    file.value = null
    prevIdx.value = -1
    setTimeout(() => uni.navigateTo({ url: `/pages/task/detail?id=${task.id}` }), 400)
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: e?.message || '提交失败', icon: 'none' })
  } finally { submitting.value = false }
}

/* ---------- 粘贴即时检测 ---------- */
const pasteText = ref('')
const pasteResult = ref(null)
const pasteChecking = ref(false)
const pasteTooLong = computed(() => pasteText.value.length > PASTE_MAX)
const pasteShort = computed(() => pasteText.value.trim().length > 0 && pasteText.value.trim().length < 120)

async function checkPaste() {
  const t = pasteText.value.trim()
  if (!t) return uni.showToast({ title: '请粘贴或输入文本', icon: 'none' })
  if (t.length > PASTE_MAX) return uni.showToast({ title: `超过 ${PASTE_MAX} 字，请分段`, icon: 'none' })
  pasteChecking.value = true
  pasteResult.value = null
  try { pasteResult.value = await detectTextDirect(t) }
  catch (e) { uni.showToast({ title: e?.message || '检测失败', icon: 'none' }) }
  finally { pasteChecking.value = false }
}
function clearPaste() { pasteText.value = ''; pasteResult.value = null }
function pasteFromClipboard() {
  uni.getClipboardData({ success: (r) => { if (r.data) { pasteText.value = (r.data || '').slice(0, PASTE_MAX + 500); pasteResult.value = null } } })
}
const pasteVerdict = computed(() => {
  const r = pasteResult.value
  if (!r) return null
  const p = r.calibratedProb ?? 0
  const risk = paragraphRisk(p)
  return {
    pct: (p * 100).toFixed(1),
    color: risk.color,
    label: r.riskLevel === 'high' ? '高疑似 AI 生成' : r.riskLevel === 'medium' ? '中等疑似' : '更像人写',
    hint: r.riskLevel === 'high' ? '这一段很可能被判 AI，建议用自己的话重写核心观点' : r.riskLevel === 'medium' ? '处在灰区，补充具体细节与个人判断会更稳' : '继续保持，具体、有细节的写法最不像机器',
  }
})
function goAssistantWithPaste() {
  const t = pasteText.value.trim().slice(0, 1600)
  uni.setStorageSync('pending_assistant_prompt', `帮我分析这段为什么会得到这个判定：${t}`)
  uni.navigateTo({ url: '/pages/assistant/chat' })
}

function goDetail(id) { uni.navigateTo({ url: `/pages/task/detail?id=${id}` }) }
const rateColorOf = (t) => aiRateColor(t.aiRate, t.threshold || 25)
</script>

<template>
  <view class="page">
    <!-- 大标题 -->
    <view class="head">
      <text class="large-title">论文检测</text>
      <text class="large-sub">上传全文出报告，或粘贴一段即时看结果</text>
    </view>

    <!-- 分段 -->
    <view class="seg">
      <view class="seg-item" :class="{ active: mode === 'file' }" @click="mode = 'file'"><text>📄 上传论文</text></view>
      <view class="seg-item" :class="{ active: mode === 'paste' }" @click="mode = 'paste'"><text>✍️ 粘贴一段</text></view>
    </view>

    <!-- ===================== 文件模式 ===================== -->
    <template v-if="mode === 'file'">
      <!-- 投放卡 -->
      <view v-if="!file" class="drop" hover-class="drop--hover" @click="pickFile">
        <view class="drop-icon"><view class="drop-doc" /><text class="drop-plus">+</text></view>
        <text class="drop-title">选择论文文件</text>
        <text class="drop-sub">PDF · Word · TXT，最大 20MB</text>
        <view class="drop-badges">
          <text class="drop-badge">自动排除参考文献 / 图表</text>
          <text class="drop-badge">段落 + 句子级结果</text>
          <text class="drop-badge">疑似来源溯源</text>
        </view>
      </view>
      <view v-else class="picked">
        <view class="picked-ext" :style="{ background: sc.wash, color: sc.tint }"><text>{{ extOf(file.name) }}</text></view>
        <view class="picked-main">
          <text class="picked-name">{{ file.name }}</text>
          <text class="picked-meta">{{ humanBytes(file.size) }} · {{ sc.label }} · 红线 {{ sc.threshold }}%</text>
        </view>
        <text class="picked-act" @click.stop="pickFile">更换</text>
        <text class="picked-act danger" @click.stop="clearFile">移除</text>
      </view>

      <!-- 修改稿对比 -->
      <view v-if="prevTasks.length" class="prev" :class="{ on: parentTask }">
        <view class="prev-head">
          <text class="prev-title">这是修改稿？</text>
          <text class="prev-sub">关联上一次，报告里直接看「比上次 −X%」和逐段变化</text>
        </view>
        <picker mode="selector" :range="prevLabels" :value="prevIdx + 1" @change="onPrevChange">
          <view class="prev-picker">
            <text class="prev-value">{{ prevLabels[prevIdx + 1] }}</text>
            <text class="prev-chevron">⌄</text>
          </view>
        </picker>
      </view>

      <!-- 最近检测 -->
      <view v-if="recent.length" class="recent">
        <text class="group-label">最近检测</text>
        <view v-for="t in recent" :key="t.id" class="recent-item" hover-class="recent-item--hover" @click="goDetail(t.id)">
          <view class="recent-main">
            <text class="recent-title">{{ t.paperTitle }}</text>
            <text class="recent-meta">{{ t.createdAt }} · {{ SCENARIO_MAP[t.scenario]?.label || t.scenario }}</text>
          </view>
          <text v-if="t.status === 'DONE' && t.aiRate != null" class="recent-rate" :style="{ color: rateColorOf(t) }">{{ t.aiRate.toFixed(1) }}%</text>
          <text v-else class="recent-rate muted">{{ t.status === 'FAILED' ? '失败' : '检测中' }}</text>
          <text class="recent-arrow">›</text>
        </view>
      </view>

      <view class="spacer" />

      <!-- 底部固定 CTA -->
      <view class="cta-bar">
        <button class="cta" :class="{ ready: file }" :loading="submitting" :disabled="!file || submitting" @click="submit">
          {{ file ? '开始检测' : '先选择论文文件' }}
        </button>
        <text class="privacy">原文加密存储，30 天自动删除 · 报告保留 3 年</text>
      </view>
    </template>

    <!-- ===================== 粘贴模式 ===================== -->
    <template v-else>
      <view class="group-head">
        <text class="group-label">段落文本</text>
        <text class="group-hint" :class="{ over: pasteTooLong }">{{ pasteText.length }} / {{ PASTE_MAX }}</text>
      </view>
      <view class="paste">
        <textarea
          v-model="pasteText" class="paste-input" auto-height :maxlength="PASTE_MAX + 500"
          placeholder="粘贴 120–5000 字，立刻看到 AI 率、句子级高亮和疑似来源。不落库、不生成任务。"
          placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="40" :adjust-position="true"
        />
        <view class="paste-tools">
          <text class="paste-tool" @click="pasteFromClipboard">📋 从剪贴板粘贴</text>
          <text v-if="pasteText" class="paste-tool" @click="clearPaste">清空</text>
        </view>
      </view>
      <text v-if="pasteShort" class="paste-warn">不足 120 字时判定不可靠，结果仅供参考</text>

      <!-- 结果 -->
      <view v-if="pasteResult && pasteVerdict" class="result">
        <view class="result-head">
          <view class="result-rate-wrap">
            <text class="result-rate" :style="{ color: pasteVerdict.color }">{{ pasteVerdict.pct }}<text class="result-unit">%</text></text>
            <text class="result-cap">校准概率</text>
          </view>
          <view class="result-meta">
            <text class="result-verdict" :style="{ color: pasteVerdict.color }">{{ pasteVerdict.label }}</text>
            <text class="result-hint">{{ pasteVerdict.hint }}</text>
            <text v-if="pasteResult.warning" class="result-warn">{{ pasteResult.warning }}</text>
          </view>
        </view>
        <view v-if="pasteResult.sentences?.length" class="result-text">
          <text v-for="s in pasteResult.sentences" :key="s.sentenceIdx" :style="{ background: paragraphRisk(s.aiProb).bg }">{{ s.text }}</text>
        </view>
        <view class="result-legend"><view class="sw high" /><text>高</text><view class="sw mid" /><text>中</text><text class="legend-note">按句着色</text></view>
        <view v-if="pasteResult.branchScores" class="result-branches">
          <text v-for="(v, k) in pasteResult.branchScores" :key="k" class="branch">{{ k }} <text class="branch-val">{{ (Number(v) * 100).toFixed(0) }}%</text></text>
        </view>
        <view class="result-actions">
          <button class="btn-tinted" @click="goAssistantWithPaste">问助手为什么</button>
          <button class="btn-tinted" @click="mode = 'file'">上传全文出报告</button>
        </view>
      </view>

      <view class="spacer" />
      <view class="cta-bar">
        <button class="cta" :class="{ ready: pasteText.trim() && !pasteTooLong }" :loading="pasteChecking" :disabled="!pasteText.trim() || pasteTooLong || pasteChecking" @click="checkPaste">即时检测</button>
        <text class="privacy">粘贴文本不落库、不生成任务，仅即时预览</text>
      </view>
    </template>

    <AssistantFab bottom="300rpx" />
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 0;
  background: linear-gradient(180deg, #EEF4FF 0%, $bg-grouped-primary 320rpx);
}
.spacer { height: 260rpx; }

/* 标题 */
.head { padding: $sp-4 $sp-1 $sp-3; }
.large-title { display: block; font-size: $fs-large-title; font-weight: $fw-bold; letter-spacing: $tracking-tight; color: $label-primary; line-height: $lh-tight; }
.large-sub { display: block; font-size: $fs-subhead; color: $label-secondary; margin-top: $sp-1; }

/* 分段 */
.seg { display: flex; padding: 6rpx; background: $fill-tertiary; border-radius: $radius-btn; margin-bottom: $sp-2; }
.seg-item {
  flex: 1; height: 72rpx; display: flex; align-items: center; justify-content: center; border-radius: 16rpx;
  text { font-size: $fs-callout; color: $label-secondary; font-weight: $fw-medium; }
  &.active { background: $bg-primary; box-shadow: 0 3rpx 8rpx rgba(0, 0, 0, 0.06); text { color: $label-primary; font-weight: $fw-semibold; } }
}

/* 分组标题 */
.group-head { display: flex; justify-content: space-between; align-items: baseline; padding: $sp-5 $sp-2 $sp-2; }
.group-label { font-size: $fs-footnote; font-weight: $fw-medium; color: $label-secondary; text-transform: uppercase; letter-spacing: $tracking-wide; }
.group-hint { font-size: $fs-caption-1; color: $label-secondary; font-variant-numeric: tabular-nums; &.over { color: $danger-solid; } }
.strong { font-weight: $fw-bold; }

/* 投放卡 */
.drop {
  @include card; margin-top: $sp-4; padding: $sp-8 $sp-4 $sp-5;
  display: flex; flex-direction: column; align-items: center; text-align: center;
  border: 2rpx dashed rgba(0, 122, 255, 0.35); background: rgba(255, 255, 255, 0.9);
  &--hover { background: $brand-primary-wash; }
}
.drop-icon { position: relative; width: 120rpx; height: 120rpx; margin-bottom: $sp-3; }
.drop-doc { position: absolute; left: 22rpx; top: 8rpx; width: 76rpx; height: 100rpx; border-radius: 12rpx; background: $brand-primary-wash; border: 3rpx solid rgba(0, 122, 255, 0.45); }
.drop-plus { position: absolute; right: 2rpx; bottom: 0; width: 48rpx; height: 48rpx; border-radius: $radius-pill; background: $brand-primary; color: #fff; font-size: $fs-title-3; line-height: 48rpx; text-align: center; box-shadow: $shadow-lift; }
.drop-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.drop-sub { font-size: $fs-footnote; color: $label-secondary; margin-top: 4rpx; }
.drop-badges { display: flex; flex-wrap: wrap; justify-content: center; gap: $sp-1; margin-top: $sp-3; }
.drop-badge { font-size: $fs-caption-2; color: $label-secondary; background: $fill-quaternary; padding: 4rpx $sp-2; border-radius: $radius-pill; }

.picked {
  @include card; margin-top: $sp-4; padding: $sp-3 $sp-4;
  display: flex; align-items: center; gap: $sp-3;
}
.picked-ext { flex: none; width: 80rpx; height: 80rpx; border-radius: $radius-md; display: flex; align-items: center; justify-content: center; font-size: $fs-caption-1; font-weight: $fw-bold; }
.picked-main { flex: 1; min-width: 0; }
.picked-name { display: block; font-size: $fs-subhead; font-weight: $fw-medium; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.picked-meta { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-top: 4rpx; }
.picked-act { flex: none; font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-medium; &.danger { color: $danger-fg; } }

/* 修改稿 */
.prev { @include card; margin-top: $sp-3; padding: $sp-3 $sp-4; border: 2rpx solid transparent; &.on { border-color: rgba(0, 122, 255, 0.35); } }
.prev-head { margin-bottom: $sp-2; }
.prev-title { display: block; font-size: $fs-subhead; font-weight: $fw-semibold; color: $label-primary; }
.prev-sub { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-top: 2rpx; }
.prev-picker { display: flex; align-items: center; justify-content: space-between; height: 72rpx; padding: 0 $sp-3; border-radius: $radius-md; background: $fill-tertiary; }
.prev-value { font-size: $fs-footnote; color: $label-primary; flex: 1; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.prev-chevron { color: $label-tertiary; font-size: $fs-subhead; margin-left: $sp-2; }

/* 最近 */
.recent { margin-top: $sp-4; .group-label { display: block; padding: 0 $sp-2 $sp-2; } }
.recent-item { @include card; padding: $sp-3 $sp-4; margin-bottom: $sp-2; display: flex; align-items: center; gap: $sp-2; &--hover { background: $fill-quaternary; } }
.recent-main { flex: 1; min-width: 0; }
.recent-title { display: block; font-size: $fs-subhead; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.recent-meta { display: block; font-size: $fs-caption-2; color: $label-secondary; margin-top: 2rpx; }
.recent-rate { flex: none; font-size: $fs-headline; font-weight: $fw-bold; font-variant-numeric: tabular-nums; &.muted { font-size: $fs-caption-1; font-weight: $fw-medium; color: $label-secondary; } }
.recent-arrow { color: $label-tertiary; font-size: $fs-title-3; }

/* CTA */
.cta-bar {
  position: fixed; left: 0; right: 0; bottom: 100rpx;   /* tabBar 之上 */
  padding: $sp-3 $sp-4;
  @include backdrop-blur($blur-material, rgba(255, 255, 255, 0.85));
  border-top: $stroke-hairline solid $separator;
  z-index: $z-sticky;
}
.cta {
  margin: 0; height: 96rpx; line-height: 96rpx; border-radius: $radius-pill;
  background: $fill-secondary; color: $label-tertiary; font-size: $fs-headline; font-weight: $fw-semibold;
  &::after { border: none; }
  &.ready { background: $brand-primary; color: #fff; box-shadow: 0 8rpx 20rpx rgba(0, 122, 255, 0.28); }
  &[disabled] { opacity: 1; }
}
.privacy { display: block; margin-top: $sp-2; font-size: $fs-caption-2; color: $label-tertiary; text-align: center; }

/* 粘贴 */
.paste { @include card; padding: $sp-3 $sp-4 $sp-2; }
.paste-input { width: 100%; min-height: 320rpx; font-size: $fs-callout; line-height: $lh-normal; color: $label-primary; }
.paste-tools { display: flex; gap: $sp-4; padding-top: $sp-2; border-top: $stroke-hairline solid $separator; margin-top: $sp-2; }
.paste-tool { font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-medium; }
.paste-warn { display: block; font-size: $fs-caption-1; color: $warning-fg; padding: $sp-2 $sp-2 0; }

.result { @include card; margin-top: $sp-4; padding: $sp-4; }
.result-head { display: flex; align-items: center; gap: $sp-4; padding-bottom: $sp-3; border-bottom: $stroke-hairline solid $separator; margin-bottom: $sp-3; }
.result-rate-wrap { flex: none; display: flex; flex-direction: column; align-items: center; }
.result-rate { font-size: 80rpx; font-weight: $fw-bold; letter-spacing: $tracking-tight; font-variant-numeric: tabular-nums; line-height: 1; }
.result-unit { font-size: 32rpx; font-weight: $fw-semibold; margin-left: 2rpx; }
.result-cap { font-size: $fs-caption-2; color: $label-secondary; margin-top: 4rpx; }
.result-meta { flex: 1; min-width: 0; }
.result-verdict { display: block; font-size: $fs-headline; font-weight: $fw-semibold; }
.result-hint { display: block; font-size: $fs-footnote; color: $label-secondary; line-height: $lh-normal; margin-top: 4rpx; }
.result-warn { display: block; font-size: $fs-caption-1; color: $warning-fg; margin-top: 4rpx; }
.result-text { font-size: $fs-body; line-height: $lh-relaxed; color: $label-primary; }
.result-legend { display: flex; align-items: center; gap: 8rpx; margin-top: $sp-2; font-size: $fs-caption-2; color: $label-secondary; }
.sw { width: 24rpx; height: 12rpx; border-radius: 4rpx; &.high { background: rgba(255, 59, 48, 0.3); } &.mid { background: rgba(255, 149, 0, 0.3); margin-left: $sp-2; } }
.legend-note { margin-left: auto; }
.result-branches { display: flex; flex-wrap: wrap; gap: $sp-2; margin-top: $sp-3; }
.branch { background: $fill-tertiary; padding: 6rpx $sp-2; border-radius: $radius-pill; font-size: $fs-caption-1; color: $label-secondary; font-variant-numeric: tabular-nums; }
.branch-val { color: $label-primary; font-weight: $fw-semibold; margin-left: 4rpx; }
.result-actions { display: flex; gap: $sp-2; margin-top: $sp-3; }
.btn-tinted {
  flex: 1; margin: 0; height: 76rpx; line-height: 76rpx; border-radius: $radius-pill;
  background: $brand-primary-wash; color: $brand-primary; font-size: $fs-subhead; font-weight: $fw-semibold;
  &::after { border: none; }
}
</style>
