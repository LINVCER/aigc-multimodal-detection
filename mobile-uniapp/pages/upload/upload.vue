<script setup>
import { ref, computed } from 'vue'
import { uploadPaper } from '@/api/detect'
import { DEGREE_MAP } from '@/utils/constants'

const DEGREES = [
  { key: 'BACHELOR', label: '本科', threshold: 20 },
  { key: 'MASTER',   label: '硕士', threshold: 15 },
  { key: 'PHD',      label: '博士', threshold: 10 },
]

const degree = ref('BACHELOR')
const file = ref(null)
const submitting = ref(false)
const threshold = computed(() => DEGREES.find(d => d.key === degree.value)?.threshold)

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

    <!-- Group 1: 学位类型（Segmented） -->
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

    <!-- Group 2: 论文文件 -->
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

    <!-- Action Button -->
    <button
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
</style>
