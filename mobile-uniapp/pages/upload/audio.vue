<script setup>
import { ref, computed } from 'vue'
import { uploadPaper } from '@/api/detect'
import { requestAndSaveSubscribe } from '@/api/wechat'

// Wave 3.3 · 微信订阅消息模板 ID（占位 · 上线前替换）
const DETECT_DONE_TMPL = 'PLACEHOLDER_DETECT_DONE'
import { useAuth } from '@/store/auth'

const auth = useAuth()
const file = ref(null)
const submitting = ref(false)

const AUDIO_EXT = ['mp3', 'wav', 'm4a', 'flac', 'ogg', 'webm']
const MAX_MB = 50

function pickFile() {
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({
    count: 1, type: 'file',
    extension: AUDIO_EXT.map(e => '.' + e),
    success: (res) => {
      const f = res.tempFiles[0]
      if (f.size > MAX_MB * 1024 * 1024) return uni.showToast({ title: `音频不能超过 ${MAX_MB}MB`, icon: 'none' })
      file.value = { path: f.path, name: f.name, size: f.size }
    },
  })
  // #endif

  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'audio/*'
  input.onchange = (e) => {
    const f = e.target.files[0]
    if (!f) return
    if (f.size > MAX_MB * 1024 * 1024) return uni.showToast({ title: `音频不能超过 ${MAX_MB}MB`, icon: 'none' })
    const url = URL.createObjectURL(f)
    file.value = { path: url, name: f.name, size: f.size }
  }
  input.click()
  // #endif
}

async function submit() {
  if (!file.value) return uni.showToast({ title: '请先选择音频文件', icon: 'none' })
  submitting.value = true
  uni.showLoading({ title: '上传中…', mask: true })
  try {
    const task = await uploadPaper(file.value.path, file.value.name, 'other', auth.userId, 'audio')
    uni.hideLoading()
    if (!task?.id) throw new Error('提交成功但未拿到任务号')
    requestAndSaveSubscribe([DETECT_DONE_TMPL])
    uni.showToast({ title: '提交成功', icon: 'success', duration: 800 })
    file.value = null
    setTimeout(() => uni.navigateTo({ url: `/pages/task/detail?id=${task.id}` }), 500)
  } catch (e) {
    uni.hideLoading()
    uni.showToast({ title: e?.message || '提交失败', icon: 'none' })
  } finally { submitting.value = false }
}

function humanBytes(n) {
  if (!n) return ''
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/upload/upload' })
}
</script>

<template>
  <view class="page">
    <view class="back-bar" hover-class="back-bar-hover" @click="goBack">
      <text class="back-arrow">‹</text>
      <text class="back-text">检测方式</text>
    </view>

    <view class="hero-header">
      <text class="large-title">音频检测</text>
      <text class="hero-sub">段级 AI 语音判定 · TTS / 克隆音色识别</text>
    </view>

    <!-- 文件区 -->
    <text class="group-label">音频文件</text>
    <view class="group-card">
      <view class="file-row" hover-class="file-row-hover" @click="pickFile">
        <view v-if="!file" class="file-empty">
          <view class="file-icon file-icon-empty" />
          <view class="file-empty-text">
            <text class="file-empty-title">选择音频</text>
            <text class="file-empty-sub">MP3 / WAV / M4A / FLAC · 最大 {{ MAX_MB }}MB</text>
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

    <text class="footnote">
      音频按 3 秒窗口切段，逐段给出 AI 生成概率与疑似来源（TTS / 克隆音色 / 真人）
    </text>

    <!-- 提交 CTA -->
    <button
      class="btn-primary submit-cta"
      :loading="submitting"
      :disabled="!file || submitting"
      @click="submit"
    >提交检测</button>

    <text class="privacy">
      音频原文加密存储，30 天后自动删除；报告保留 3 年
    </text>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

.back-bar {
  display: flex; align-items: center;
  height: 60rpx;
  padding: 0 $sp-1;
  margin-bottom: $sp-1;
  transition: opacity $duration-fast;
}
.back-bar-hover { opacity: 0.6; }
.back-arrow {
  font-size: 44rpx;
  color: $brand-primary;
  line-height: 1;
  margin-right: 4rpx;
}
.back-text {
  font-size: $fs-callout;
  color: $brand-primary;
  font-weight: $fw-medium;
}

.hero-header { padding: $sp-1 $sp-1 $sp-3; }
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

.group-label {
  display: block;
  padding: $sp-5 $sp-3 $sp-2;
  font-size: $fs-footnote;
  font-weight: $fw-medium;
  color: $label-secondary;
  text-transform: uppercase;
  letter-spacing: $tracking-wide;
}
.group-card { @include card-flush; }

.file-row {
  padding: $sp-4;
  transition: background $duration-fast $ease-standard;
}
.file-row-hover { background: rgba(60, 60, 67, 0.05); }
.file-empty, .file-picked { display: flex; align-items: center; }

.file-icon {
  position: relative;
  width: 72rpx; height: 72rpx;
  border-radius: $radius-md;
  margin-right: $sp-3;
  flex-shrink: 0;
}
.file-icon-empty {
  background: rgba(255, 45, 85, 0.10) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FF2D55' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M9 18V5l12-2v13'/><circle cx='6' cy='18' r='3'/><circle cx='18' cy='16' r='3'/></svg>") no-repeat center / 44rpx 44rpx;
}
.file-icon-picked {
  background: rgba(52, 199, 89, 0.14) url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%231B7F3E' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M9 18V5l12-2v13'/><circle cx='6' cy='18' r='3'/><circle cx='18' cy='16' r='3'/><polyline points='4 4 8 8 12 4' transform='translate(6 6) scale(0.4)'/></svg>") no-repeat center / 44rpx 44rpx;
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
.chevron { color: $label-tertiary; font-size: $icon-md; margin-left: $sp-2; }
.reselect {
  color: $brand-primary; font-size: $fs-subhead;
  font-weight: $fw-medium; margin-left: $sp-2;
}

.footnote {
  display: block;
  font-size: $fs-caption-1;
  color: $label-secondary;
  padding: $sp-2 $sp-3 0;
  line-height: $lh-normal;
}

.btn-primary { @include btn-primary; }
.submit-cta { margin-top: $sp-6; }

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
