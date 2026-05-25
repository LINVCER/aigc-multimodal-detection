<template>
  <view class="container">
    <view class="record-area">
      <view class="record-btn" @touchstart="startRecord" @touchend="stopRecord">
        <text class="record-icon">{{ recording ? '⏹' : '🎤' }}</text>
        <text>{{ recording ? '录制中...松手停止' : '按住录音' }}</text>
      </view>
    </view>
    <view v-if="audioPath" style="margin-top:24rpx;text-align:center;color:#718096">
      已录制音频 ({{ duration }}秒)
    </view>
    <button type="primary" @click="handleDetect" :loading="detecting" :disabled="!audioPath" style="margin-top:24rpx">
      开始检测
    </button>
  </view>
</template>

<script>
import CONFIG from "../config.js"

export default {
  data() {
    return { audioPath: "", recording: false, detecting: false, duration: 0, recorder: null }
  },
  methods: {
    startRecord() {
      this.recording = true
      this.recorder = uni.getRecorderManager()
      this.recorder.start({ format: 'wav', sampleRate: 16000 })
    },
    stopRecord() {
      this.recording = false
      this.recorder.stop()
      this.recorder.onStop((res) => {
        this.audioPath = res.tempFilePath
        this.duration = Math.round(res.duration)
      })
    },
    async handleDetect() {
      if (!this.audioPath) { uni.showToast({ title: "请先录音", icon: "none" }); return }
      this.detecting = true
      const token = uni.getStorageSync("access_token")
      uni.uploadFile({
        url: `${CONFIG.API_BASE}/detect/audio`,
        filePath: this.audioPath,
        name: 'file',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (res) => {
          const data = JSON.parse(res.data)
          uni.showToast({ title: "检测已提交", icon: "success" })
          uni.navigateTo({ url: `/pages/result/result?taskId=${data.task_id}&modality=audio` })
          this.detecting = false
        },
        fail: () => { uni.showToast({ title: "上传失败", icon: "error" }); this.detecting = false }
      })
    }
  }
}
</script>

<style scoped>
.container { padding: 24rpx; }
.record-area { display: flex; justify-content: center; padding: 80rpx 0; }
.record-btn { width: 240rpx; height: 240rpx; border-radius: 50%; background: #409EFF; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; font-size: 24rpx; }
.record-icon { font-size: 64rpx; margin-bottom: 12rpx; }
</style>
