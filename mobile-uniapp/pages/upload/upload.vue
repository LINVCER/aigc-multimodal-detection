<script setup>
import { ref, computed } from 'vue'
import { uploadPaper } from '@/api/detect'

const DEGREES = [
  { key: 'BACHELOR', label: '本科', threshold: 20 },
  { key: 'MASTER',   label: '硕士', threshold: 15 },
  { key: 'PHD',      label: '博士', threshold: 10 },
]

const degree = ref('BACHELOR')
const file = ref(null)          // { path, name, size }
const submitting = ref(false)

const threshold = computed(() => DEGREES.find(d => d.key === degree.value)?.threshold)

/**
 * 选文件
 *   小程序端优先用 chooseMessageFile（从聊天转发），H5 端 fallback 到 chooseFile
 */
function pickFile() {
  // #ifdef MP-WEIXIN
  uni.chooseMessageFile({
    count: 1,
    type: 'file',
    extension: ['.pdf', '.doc', '.docx', '.txt'],
    success: (res) => {
      const f = res.tempFiles[0]
      if (f.size > 20 * 1024 * 1024) {
        uni.showToast({ title: '文件不能超过 20MB', icon: 'none' })
        return
      }
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
    if (f.size > 20 * 1024 * 1024) {
      uni.showToast({ title: '文件不能超过 20MB', icon: 'none' })
      return
    }
    const url = URL.createObjectURL(f)
    file.value = { path: url, name: f.name, size: f.size }
  }
  input.click()
  // #endif
}

async function submit() {
  if (!file.value) {
    uni.showToast({ title: '请先选择论文文件', icon: 'none' })
    return
  }
  submitting.value = true
  try {
    await uploadPaper(file.value.path, file.value.name, degree.value)
    uni.showToast({ title: '提交成功', icon: 'success' })
    file.value = null
    setTimeout(() => uni.switchTab({ url: '/pages/index/index' }), 800)
  } catch (e) {
    uni.showToast({ title: e?.message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <view class="container">
    <text class="section-title">学位类型</text>
    <view class="degree-row">
      <view
        v-for="d in DEGREES" :key="d.key"
        class="chip" :class="{ active: degree === d.key }"
        @click="degree = d.key"
      >{{ d.label }}</view>
    </view>
    <text class="threshold-hint">教育部红线：AI 率 ≤ {{ threshold }}%</text>

    <text class="section-title">论文文件</text>
    <view class="file-box" @click="pickFile">
      <text class="file-icon">{{ file ? '📄' : '📎' }}</text>
      <text class="file-name">
        {{ file ? file.name : '点击选择 PDF / Word / TXT（≤ 20MB）' }}
      </text>
    </view>

    <button
      class="submit"
      :disabled="!file || submitting"
      :loading="submitting"
      @click="submit"
    >提交检测</button>

    <text class="privacy">论文原文加密存储，30 天后自动删除；检测报告保留 3 年</text>
  </view>
</template>

<style lang="scss" scoped>
.container {
  padding: 40rpx;
  background: #fff;
  min-height: 100vh;
}

.section-title {
  display: block;
  font-size: 28rpx;
  font-weight: 600;
  color: #374151;
  margin: 40rpx 0 20rpx;
}

.degree-row {
  display: flex;
  gap: 20rpx;
}
.chip {
  padding: 20rpx 40rpx;
  border-radius: 40rpx;
  border: 1rpx solid #d1d5db;
  font-size: 28rpx;
  color: #374151;
  &.active {
    background: #1a56db;
    color: #fff;
    border-color: #1a56db;
    font-weight: 600;
  }
}

.threshold-hint {
  display: block;
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #f59e0b;
}

.file-box {
  border: 3rpx dashed #d1d5db;
  border-radius: 20rpx;
  padding: 72rpx 20rpx;
  text-align: center;
  background: #f9fafb;
}
.file-icon { display: block; font-size: 64rpx; margin-bottom: 16rpx; }
.file-name { display: block; font-size: 26rpx; color: #6b7280; }

.submit {
  margin-top: 56rpx;
  background: #1a56db;
  color: #fff;
  font-size: 32rpx;
  font-weight: 600;
  border-radius: 16rpx;
  &[disabled] { opacity: 0.4; }
}

.privacy {
  display: block;
  margin-top: 32rpx;
  font-size: 22rpx;
  color: #9ca3af;
  text-align: center;
}
</style>
