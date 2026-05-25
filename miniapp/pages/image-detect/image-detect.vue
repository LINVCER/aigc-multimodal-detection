<template>
  <view class="container">
    <view class="upload-area" @click="chooseImage">
      <image v-if="imagePath" :src="imagePath" mode="aspectFit" class="preview" />
      <text v-else class="placeholder">点击选择图片 或 拍照</text>
    </view>
    <button type="primary" @click="handleDetect" :loading="detecting" :disabled="!imagePath" style="margin-top:24rpx">
      开始检测
    </button>
  </view>
</template>

<script>
import CONFIG from "../config.js"

export default {
  data() {
    return { imagePath: "", detecting: false }
  },
  methods: {
    async chooseImage() {
      const [err, res] = await uni.chooseImage({ count: 1, sourceType: ['album', 'camera'] })
      if (res.tempFilePaths) this.imagePath = res.tempFilePaths[0]
    },
    async handleDetect() {
      if (!this.imagePath) { uni.showToast({ title: "请选择图片", icon: "none" }); return }
      this.detecting = true
      const token = uni.getStorageSync("access_token")
      uni.uploadFile({
        url: `${CONFIG.API_BASE}/detect/image`,
        filePath: this.imagePath,
        name: 'file',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success: (res) => {
          const data = JSON.parse(res.data)
          uni.showToast({ title: "检测已提交: " + data.task_id, icon: "success" })
          // 跳转到结果页
          uni.navigateTo({ url: `/pages/result/result?taskId=${data.task_id}&modality=image` })
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
.upload-area { width: 100%; height: 500rpx; border: 2px dashed #cbd5e0; border-radius: 12rpx; display: flex; align-items: center; justify-content: center; }
.preview { width: 100%; height: 100%; border-radius: 12rpx; }
.placeholder { color: #a0aec0; font-size: 28rpx; }
</style>
