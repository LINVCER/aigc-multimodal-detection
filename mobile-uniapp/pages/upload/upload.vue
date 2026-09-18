<script setup>
import { ref, computed } from 'vue'
import { uploadPaper, detectTextDirect } from '@/api/detect'
import { SCENARIO_MAP, paragraphRisk } from '@/utils/constants'
import { useAuth } from '@/store/auth'

const auth = useAuth()

// W3.b · 使用场景预设（取代原学位红线）
const SCENARIOS = [
  { key: 'academic_bachelor', label: '学术·本科', threshold: 20, desc: '毕业论文自查' },
  { key: 'academic_master',   label: '学术·硕士', threshold: 15, desc: '硕士毕业论文' },
  { key: 'academic_phd',      label: '学术·博士', threshold: 10, desc: '博士毕业论文' },
  { key: 'job_report',        label: '职业报告',   threshold: 15, desc: '工作报告 / PR件' },
  { key: 'self_media',        label: '自媒体',     threshold: 30, desc: '公众号 / 小红书' },
  { key: 'other',             label: '其他',       threshold: 25, desc: '通用文档' },
]

const mode = ref('file')  // file | paste
const scenario = ref('academic_bachelor')
const file = ref(null)
const submitting = ref(false)
const threshold = computed(() => SCENARIOS.find(s => s.key === scenario.value)?.threshold)

// 粘贴模式
const PASTE_MAX = 5000
const pasteText = ref('')
const pasteResult = ref(null)
const pasteChecking = ref(false)

async function checkPaste() {
  const t = pasteText.value.trim()
  if (!t) return uni.showToast({ title: '请粘贴或输入文本', icon: 'none' })
  if (t.length > PASTE_MAX) return uni.showToast({ title: `文本超过 ${PASTE_MAX} 字，请分段`, icon: 'none' })
  pasteChecking.value = true
  pasteResult.value = null
  try {
    pasteResult.value = await detectTextDirect(t)
  } catch (e) {
    uni.showToast({ title: e?.message || '检测失败', icon: 'none' })
  } finally { pasteChecking.value = false }
}
function clearPaste() { pasteText.value = ''; pasteResult.value = null }

function pickFile() {
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({
    count: 1, type: 'file',
    extension: ['.pdf', '.doc', '.docx', '.txt'],
    success: (res) => {
      const f = res.tempFiles[0]
      if (f.size > 20 * 1024 * 1024) return uni.showToast({ title: '文件不能超过 20MB', icon: 'none' })
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
    if (f.size > 20 * 1024 * 1024) return uni.showToast({ title: '文件不能超过 20MB', icon: 'none' })
    const url = URL.createObjectURL(f)
    file.value = { path: url, name: f.name, size: f.size }
  }
  input.click()
  // #endif
}

async function submit() {
  if (!file.value) return uni.showToast({ title: '请先选择论文文件', icon: 'none' })
  submitting.value = true
  uni.showLoading({ title: '上传中…', mask: true })
  try {
    const task = await uploadPaper(file.value.path, file.value.name, scenario.value, auth.userId)
    uni.hideLoading()
    if (!task?.id) throw new Error('提交成功但未拿到任务号')
    uni.showToast({ title: '提交成功', icon: 'success', duration: 800 })
    file.value = null
    setTimeout(() => uni.navigateTo({ url: `/pages/task/detail?id=${task.id}` }), 500)
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: e?.message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}

function humanBytes(n) {
  if (!n) return ''
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

function scenarioOf(k) { return SCENARIO_MAP[k] || SCENARIO_MAP.other }
</script>

<template>
  <view class="page">
    <!-- Large Title -->
    <view class="hero-header">
      <text class="large-title">上传检测</text>
      <text class="hero-sub">选择场景 · 上传或粘贴，几十秒拿到 AI 率报告</text>
    </view>

    <!-- Mode Segmented：文件 / 粘贴 -->
    <view class="mode-tabs">
      <view class="mode-seg" :class="{ active: mode === 'file' }" @click="mode = 'file'">
        <text>文件</text>
      </view>
      <view class="mode-seg" :class="{ active: mode === 'paste' }" @click="mode = 'paste'">
        <text>粘贴</text>
      </view>
    </view>

    <!-- ============ 文件模式 ============ -->
    <template v-if="mode === 'file'">
      <text class="group-label">使用场景</text>
      <view class="scenario-card">
        <view class="scenario-grid">
          <view
            v-for="s in SCENARIOS" :key="s.key"
            class="scenario-tile"
            :class="{ active: scenario === s.key }"
            :style="scenario === s.key ? { borderColor: scenarioOf(s.key).tint, background: scenarioOf(s.key).wash } : {}"
            @click="scenario = s.key"
          >
            <text class="scenario-label">{{ s.label }}</text>
            <text class="scenario-desc">{{ s.desc }}</text>
            <text class="scenario-th">≤ {{ s.threshold }}%</text>
          </view>
        </view>
      </view>
      <text class="footnote">
        当前场景建议 AI 率 <text class="footnote-strong">≤ {{ threshold }}%</text>
      </text>

      <text class="group-label">论文文件</text>
      <view class="group-card">
        <view class="file-row" hover-class="file-row-hover" @click="pickFile">
          <view v-if="!file" class="file-empty">
            <view class="file-icon file-icon-empty" />
            <view class="file-empty-text">
              <text class="file-empty-title">选择文件</text>
              <text class="file-empty-sub">PDF / Word / TXT · 最大 20MB</text>
            </view>
            <text class="chevron">›</text>
          </view>
          <view v-else class="file-picked">
            <view class="file-icon file-icon-picked" />
            <view class="file-info">
              <text class="file-name">{{ file.name }}</text>
              <text class="file-size">{{ humanBytes(file.size) }}</text>
            </view>
            <text class="reselect">更换</text>
          </view>
        </view>
      </view>
    </template>

    <!-- ============ 粘贴模式 ============ -->
    <template v-else>
      <view class="group-label-line">
        <text class="group-label no-pad">段落文本</text>
        <text class="paste-count" :class="{ over: pasteText.length > PASTE_MAX }">
          {{ pasteText.length }} / {{ PASTE_MAX }}
        </text>
      </view>
      <view class="paste-card">
        <textarea
          v-model="pasteText"
          class="paste-input"
          placeholder="粘贴 50-5000 字段落，即时看到 AI 率与句子级高亮"
          placeholder-style="color: rgba(60,60,67,0.30)"
          maxlength="6000"
          auto-height
        />
      </view>

      <view class="paste-actions">
        <button
          class="btn-secondary"
          @click="clearPaste"
          :disabled="!pasteText && !pasteResult"
        >清空</button>
        <button
          class="btn-primary"
          :loading="pasteChecking"
          :disabled="!pasteText.trim() || pasteText.length > PASTE_MAX"
          @click="checkPaste"
        >即时检测</button>
      </view>

      <template v-if="pasteResult">
        <text class="group-label">检测结果</text>
        <view class="paste-result-card">
          <view class="paste-result-head">
            <text class="paste-result-rate" :style="{ color: paragraphRisk(pasteResult.calibratedProb).color }">
              {{ (pasteResult.calibratedProb * 100).toFixed(1) }}%
            </text>
            <view class="paste-result-meta">
              <text class="paste-result-verdict" :style="{ color: paragraphRisk(pasteResult.calibratedProb).color }">
                <template v-if="pasteResult.riskLevel === 'high'">高疑似 AI 生成</template>
                <template v-else-if="pasteResult.riskLevel === 'medium'">中等疑似</template>
                <template v-else>判定人类写作</template>
              </text>
              <text v-if="pasteResult.warning" class="paste-result-warn">{{ pasteResult.warning }}</text>
            </view>
          </view>

          <view v-if="pasteResult.sentences.length" class="paste-highlight">
            <text
              v-for="s in pasteResult.sentences" :key="s.sentenceIdx"
              :style="{ background: paragraphRisk(s.aiProb).bg }"
            >{{ s.text }}</text>
          </view>

          <view v-if="pasteResult.branchScores" class="paste-branches">
            <text
              v-for="(v, k) in pasteResult.branchScores" :key="k"
              class="branch-chip"
            >{{ k }} <text class="branch-val">{{ (Number(v) * 100).toFixed(0) }}%</text></text>
          </view>
        </view>
      </template>
    </template>

    <!-- 文件模式主 CTA -->
    <button
      v-if="mode === 'file'"
      class="btn-primary submit-cta"
      :loading="submitting"
      :disabled="!file || submitting"
      @click="submit"
    >提交检测</button>

    <text class="privacy">
      论文原文加密存储，30 天后自动删除；报告保留 3 年
    </text>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

/* ---------- Large Title Hero ---------- */
.hero-header { padding: $sp-3 $sp-1 $sp-3; }
.large-title {
  display: block;
  font-size: $fs-large-title;
  font-weight: $fw-bold;
  line-height: $lh-tight;
  letter-spacing: $tracking-tight;
  color: $label-primary;
}
.hero-sub {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-top: $sp-1;
}

/* ---------- Mode Segmented ---------- */
.mode-tabs {
  display: flex;
  padding: 6rpx;
  background: $fill-tertiary;
  border-radius: $radius-btn;
  margin-top: $sp-2;
}
.mode-seg {
  flex: 1;
  height: 72rpx;
  display: flex; align-items: center; justify-content: center;
  border-radius: 16rpx;
  transition: all $duration-fast $ease-standard;
  text {
    font-size: $fs-callout;
    color: $label-primary;
    font-weight: $fw-medium;
  }
  &.active {
    background: $bg-primary;
    box-shadow: 0 3rpx 8rpx rgba(0, 0, 0, 0.05);
    text { font-weight: $fw-semibold; }
  }
}

/* ---------- Group Label ---------- */
.group-label {
  display: block;
  padding: $sp-5 $sp-3 $sp-2;
  font-size: $fs-footnote;
  font-weight: $fw-medium;
  color: $label-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wide;
  &.no-pad { padding: 0; }
}
.group-label-line {
  padding: $sp-5 $sp-3 $sp-2;
  display: flex; justify-content: space-between; align-items: center;
}
.paste-count {
  font-size: $fs-caption-1;
  color: $label-secondary;
  font-variant-numeric: tabular-nums;
  &.over { color: $danger-solid; }
}
.group-card {
  @include card-flush;
}

/* ---------- 场景网格 ---------- */
.scenario-card {
  @include card-flush;
}
.scenario-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: $sp-2;
  padding: $sp-3;
}
.scenario-tile {
  padding: $sp-3;
  border-radius: $radius-btn;
  background: $fill-quaternary;
  border: 2rpx solid transparent;
  transition: all $duration-fast $ease-standard;
}
.scenario-label {
  display: block;
  font-size: $fs-subhead;
  font-weight: $fw-semibold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
}
.scenario-desc {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  margin-top: 6rpx;
}
.scenario-th {
  display: block;
  font-size: $fs-caption-1;
  color: $warning-solid;
  margin-top: $sp-1;
  font-weight: $fw-medium;
}

.footnote {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  padding: $sp-2 $sp-3 0;
}
.footnote-strong {
  color: $warning-solid;
  font-weight: $fw-semibold;
}

/* ---------- 文件行 ---------- */
.file-row {
  padding: $sp-4;
  transition: background $duration-fast $ease-standard;
}
.file-row-hover { background: rgba(60, 60, 67, 0.05); }
.file-empty, .file-picked {
  display: flex; align-items: center;
}
.file-icon {
  position: relative;
  width: 72rpx; height: 72rpx;
  border-radius: $radius-md;
  margin-right: $sp-3;
  flex-shrink: 0;
  /* SVG 文件图标（PDF/DOC 文档样式，折角 + 三条内容线） · 蓝色 stroke */
  background: $brand-primary-wash url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23007AFF' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><polyline points='14 3 14 8 19 8'/><line x1='8' y1='13' x2='16' y2='13'/><line x1='8' y1='17' x2='13' y2='17'/></svg>") no-repeat center / 44rpx 44rpx;
}
.file-icon-picked {
  background-color: $success-bg;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%231B7F3E' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'/><polyline points='14 3 14 8 19 8'/><polyline points='9 15 11 17 15 13'/></svg>");
}
.file-empty-text, .file-info { flex: 1; min-width: 0; }
.file-empty-title, .file-name {
  display: block;
  font-size: $fs-callout;
  color: $label-primary;
  font-weight: $fw-medium;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-empty-sub, .file-size {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  margin-top: 4rpx;
}
.chevron {
  color: $label-tertiary;
  font-size: $icon-md;
  margin-left: $sp-2;
}
.reselect {
  color: $brand-primary;
  font-size: $fs-subhead;
  font-weight: $fw-medium;
  margin-left: $sp-2;
}

/* ---------- 主 & 次按钮 ---------- */
.btn-primary   { @include btn-primary; }
.btn-secondary { @include btn-secondary; }
.submit-cta {
  margin-top: $sp-6;
}

/* ---------- 粘贴模式 ---------- */
.paste-card {
  @include card-flush;
  padding: $sp-3;
}
.paste-input {
  width: 100%;
  min-height: 320rpx;
  font-size: $fs-callout;
  line-height: $lh-normal;
  color: $label-primary;
}

.paste-actions {
  display: flex; justify-content: flex-end; gap: $sp-2;
  margin: $sp-3 0 $sp-1;
  .btn-primary, .btn-secondary {
    min-width: 200rpx;
    height: $size-btn-h-md;
    line-height: $size-btn-h-md;
    font-size: $fs-subhead;
  }
}

/* ---------- 粘贴结果卡 ---------- */
.paste-result-card {
  @include card;
  padding: $sp-4;
}
.paste-result-head {
  display: flex; align-items: center; gap: $sp-3;
  padding-bottom: $sp-3;
  border-bottom: $stroke-hairline solid $separator;
  margin-bottom: $sp-3;
}
.paste-result-rate {
  font-size: 72rpx;
  font-weight: $fw-bold;
  letter-spacing: $tracking-tight;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.paste-result-meta { flex: 1; }
.paste-result-verdict {
  display: block;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
}
.paste-result-warn {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  margin-top: 4rpx;
}

.paste-highlight {
  font-size: $fs-body;
  line-height: $lh-relaxed;
  color: $label-primary;
}

.paste-branches {
  display: flex; flex-wrap: wrap; gap: $sp-2;
  margin-top: $sp-3;
}
.branch-chip {
  background: $fill-tertiary;
  padding: 6rpx $sp-2;
  border-radius: $radius-pill;
  font-size: $fs-caption-1;
  color: $label-secondary;
  font-variant-numeric: tabular-nums;
}
.branch-val {
  color: $label-primary;
  font-weight: $fw-semibold;
  margin-left: 4rpx;
}

/* ---------- 隐私提示 ---------- */
.privacy {
  display: block;
  margin-top: $sp-4;
  font-size: $fs-caption-1;
  color: $label-secondary;
  text-align: center;
  line-height: $lh-normal;
  padding: 0 $sp-5;
}
</style>
