<script setup>
import { ref, computed } from 'vue'
import { uploadPaper, detectTextDirect } from '@/api/detect'
import { DEGREE_MAP, paragraphRisk } from '@/utils/constants'

const DEGREES = [
  { key: 'BACHELOR', label: '本科', threshold: 20 },
  { key: 'MASTER',   label: '硕士', threshold: 15 },
  { key: 'PHD',      label: '博士', threshold: 10 },
]

const mode = ref('file')  // file | paste
const degree = ref('BACHELOR')
const file = ref(null)
const submitting = ref(false)
const threshold = computed(() => DEGREES.find(d => d.key === degree.value)?.threshold)

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
  // 大文件上传给全屏遮罩，避免用户在等待时误触其它按钮
  uni.showLoading({ title: '上传中…', mask: true })
  try {
    const task = await uploadPaper(file.value.path, file.value.name, degree.value)
    uni.hideLoading()
    if (!task?.id) {
      throw new Error('提交成功但未拿到任务号')
    }
    uni.showToast({ title: '提交成功', icon: 'success', duration: 800 })
    file.value = null
    // 直接跳报告详情，用户马上看到"检测中"进度；详情页自带轮询直到 DONE
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
</script>

<template>
  <view class="page">
    <view class="large-title-bar">
      <text class="large-title">上传检测</text>
    </view>

    <!-- Mode segmented：文件 / 粘贴 -->
    <view class="mode-tabs">
      <view class="mode-seg" :class="{ active: mode === 'file' }" @click="mode = 'file'">📄 文件</view>
      <view class="mode-seg" :class="{ active: mode === 'paste' }" @click="mode = 'paste'">✍ 粘贴</view>
    </view>

    <!-- ============ 文件模式 ============ -->
    <template v-if="mode === 'file'">
      <text class="group-label">学位类型</text>
      <view class="group-card">
        <view class="segmented">
          <view
            v-for="d in DEGREES" :key="d.key"
            class="seg" :class="{ active: degree === d.key }"
            @click="degree = d.key"
          >{{ d.label }}</view>
        </view>
      </view>
      <text class="footnote">
        教育部红线：AI 率 <text class="footnote-strong">≤ {{ threshold }}%</text>
      </text>

      <text class="group-label">论文文件</text>
      <view class="group-card">
        <view class="file-row" @click="pickFile">
          <view v-if="!file" class="file-empty">
            <text class="file-icon">􀈕</text>
            <view class="file-empty-text">
              <text class="file-empty-title">选择文件</text>
              <text class="file-empty-sub">PDF / Word / TXT · 最大 20MB</text>
            </view>
            <text class="chevron">›</text>
          </view>
          <view v-else class="file-picked">
            <text class="file-icon-picked">📄</text>
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
        <text class="group-label">段落文本</text>
        <text class="paste-count" :class="{ over: pasteText.length > PASTE_MAX }">
          {{ pasteText.length }} / {{ PASTE_MAX }}
        </text>
      </view>
      <view class="group-card paste-card">
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
          class="paste-btn paste-btn-plain"
          @click="clearPaste"
          :disabled="!pasteText && !pasteResult"
        >清空</button>
        <button
          class="paste-btn paste-btn-primary"
          :loading="pasteChecking"
          :disabled="!pasteText.trim() || pasteText.length > PASTE_MAX"
          @click="checkPaste"
        >即时检测</button>
      </view>

      <!-- 粘贴结果 -->
      <template v-if="pasteResult">
        <text class="group-label">检测结果</text>
        <view class="group-card paste-result-card">
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

    <!-- Action Button（仅文件模式） -->
    <button
      v-if="mode === 'file'"
      class="submit"
      :class="{ disabled: !file || submitting }"
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
  background: #F2F2F7;
  padding: 40rpx 32rpx 100rpx;
}
.large-title-bar { padding-bottom: 32rpx; }
.large-title {
  font-size: 68rpx;
  font-weight: 700;
  letter-spacing: -1rpx;
  color: #000;
}

.group-label {
  display: block;
  font-size: 26rpx;
  font-weight: 500;
  color: rgba(60,60,67,0.60);
  text-transform: uppercase;
  letter-spacing: 1rpx;
  padding: 32rpx 20rpx 12rpx;
}
.group-card {
  background: #FFFFFF;
  border-radius: 28rpx;
  overflow: hidden;
}

/* Segmented Control（iOS 风） */
.segmented {
  display: flex;
  padding: 8rpx;
  background: rgba(120,120,128,0.12);
  border-radius: 20rpx;
  margin: 20rpx;
}
.seg {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  font-size: 30rpx;
  color: #000;
  border-radius: 16rpx;
  transition: all 200ms cubic-bezier(0.32, 0.72, 0, 1);
  &.active {
    background: #FFFFFF;
    font-weight: 600;
    box-shadow: 0 3rpx 8rpx rgba(0,0,0,0.05);
  }
}

.footnote {
  display: block;
  font-size: 24rpx;
  color: rgba(60,60,67,0.60);
  padding: 12rpx 20rpx 0;
}
.footnote-strong { color: #FF9500; font-weight: 600; }

/* 文件行 */
.file-row { padding: 32rpx; }
.file-empty, .file-picked {
  display: flex; align-items: center;
}
.file-icon {
  font-size: 40rpx;
  color: #007AFF;
  width: 72rpx; height: 72rpx;
  line-height: 72rpx;
  text-align: center;
  background: rgba(0,122,255,0.10);
  border-radius: 18rpx;
  margin-right: 24rpx;
}
.file-icon-picked {
  font-size: 40rpx;
  width: 72rpx; height: 72rpx;
  line-height: 72rpx;
  text-align: center;
  margin-right: 24rpx;
}
.file-empty-text, .file-info { flex: 1; min-width: 0; }
.file-empty-title, .file-name {
  display: block;
  font-size: 32rpx;
  color: #000;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-empty-sub, .file-size {
  display: block;
  font-size: 24rpx;
  color: rgba(60,60,67,0.60);
  margin-top: 4rpx;
}
.chevron   { color: rgba(60,60,67,0.30); font-size: 40rpx; }
.reselect  { color: #007AFF; font-size: 28rpx; font-weight: 500; }

/* 主按钮 */
.submit {
  margin-top: 48rpx;
  height: 100rpx;
  line-height: 100rpx;
  background: #007AFF;
  color: #FFFFFF;
  font-size: 34rpx;
  font-weight: 600;
  border-radius: 9999rpx;
  letter-spacing: 2rpx;
  transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1),
              opacity 200ms;
  &:active { transform: scale(0.98); opacity: 0.88; }
  &.disabled { opacity: 0.4; }
}

.privacy {
  display: block;
  margin-top: 32rpx;
  font-size: 24rpx;
  color: rgba(60,60,67,0.60);
  text-align: center;
  line-height: 1.5;
  padding: 0 40rpx;
}

/* ============ Mode Tabs（文件 / 粘贴） ============ */
.mode-tabs {
  display: flex;
  padding: 8rpx;
  background: rgba(120,120,128,0.12);
  border-radius: 24rpx;
  margin-bottom: 32rpx;
}
.mode-seg {
  flex: 1;
  text-align: center;
  padding: 20rpx 0;
  font-size: 30rpx;
  color: #000;
  border-radius: 18rpx;
  transition: all 200ms cubic-bezier(0.32, 0.72, 0, 1);
  &.active {
    background: #FFFFFF;
    font-weight: 600;
    box-shadow: 0 3rpx 8rpx rgba(0,0,0,0.05);
  }
}

/* ============ 粘贴模式 ============ */
.group-label-line {
  display: flex; justify-content: space-between; align-items: center;
  padding: 40rpx 20rpx 12rpx;
}
.group-label-line .group-label { padding: 0; }
.paste-count {
  font-size: 24rpx;
  color: rgba(60,60,67,0.60);
  font-variant-numeric: tabular-nums;
  &.over { color: #FF3B30; }
}

.paste-card { padding: 20rpx !important; }
.paste-input {
  width: 100%;
  min-height: 300rpx;
  font-size: 30rpx;
  line-height: 1.6;
  color: #000;
}

.paste-actions {
  display: flex; justify-content: flex-end; gap: 20rpx;
  margin: 20rpx 0 8rpx;
}
.paste-btn {
  min-width: 200rpx;
  height: 80rpx;
  line-height: 80rpx;
  font-size: 28rpx;
  font-weight: 600;
  border-radius: 9999rpx;
  transition: opacity 200ms, transform 200ms cubic-bezier(0.32, 0.72, 0, 1);
  &:active { transform: scale(0.96); }
  &[disabled] { opacity: 0.4; }
}
.paste-btn-plain {
  background: rgba(120,120,128,0.12);
  color: #000;
}
.paste-btn-primary {
  background: #007AFF;
  color: #fff;
}

/* 结果卡 */
.paste-result-card { padding: 32rpx !important; }
.paste-result-head {
  display: flex; align-items: center;
  gap: 24rpx;
  padding-bottom: 24rpx;
  border-bottom: 1rpx solid rgba(60,60,67,0.18);
  margin-bottom: 24rpx;
}
.paste-result-rate {
  font-size: 72rpx;
  font-weight: 700;
  letter-spacing: -1rpx;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.paste-result-meta { flex: 1; }
.paste-result-verdict { display: block; font-size: 30rpx; font-weight: 600; }
.paste-result-warn {
  display: block; font-size: 22rpx;
  color: rgba(60,60,67,0.60); margin-top: 4rpx;
}

.paste-highlight {
  font-size: 30rpx;
  line-height: 1.7;
  color: #000;
}

.paste-branches {
  display: flex; flex-wrap: wrap; gap: 12rpx;
  margin-top: 24rpx;
}
.branch-chip {
  background: rgba(120,120,128,0.14);
  padding: 6rpx 20rpx;
  border-radius: 9999rpx;
  font-size: 22rpx;
  color: rgba(60,60,67,0.60);
  font-variant-numeric: tabular-nums;
}
.branch-val { color: #000; font-weight: 600; margin-left: 4rpx; }
</style>
