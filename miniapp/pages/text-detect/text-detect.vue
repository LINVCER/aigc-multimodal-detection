<template>
  <view class="container">
    <textarea
      v-model="content"
      placeholder="请输入或粘贴需要检测的文本..."
      maxlength="50000"
      :style="{ height: '400rpx' }"
    />
    <button type="primary" @click="handleDetect" :loading="detecting" style="margin-top:24rpx">
      开始检测
    </button>

    <view v-if="result" class="result-card">
      <view class="verdict" :class="result.is_ai_generated ? 'ai' : 'human'">
        {{ result.is_ai_generated ? '疑似 AI 生成' : '可能人类写作' }}
      </view>
      <view class="confidence">置信度: {{ (result.confidence * 100).toFixed(1) }}%</view>
      <view v-if="result.risk_level" class="risk">
        风险等级: {{ { low: '低', medium: '中', high: '高' }[result.risk_level] }}
      </view>
      <view v-if="result.arbitration_warning" class="warning">
        {{ result.arbitration_warning }}
      </view>
    </view>
  </view>
</template>

<script>
import CONFIG from "../config.js"

export default {
  data() {
    return { content: "", detecting: false, result: null }
  },
  methods: {
    async handleDetect() {
      if (!this.content.trim()) { uni.showToast({ title: "请输入文本", icon: "none" }); return }
      this.detecting = true
      try {
        const token = uni.getStorageSync("access_token")
        const [err, res] = await uni.request({
          url: `${CONFIG.API_BASE}/detect/text`,
          method: "POST",
          data: { content: this.content, options: { explain: true, attribution: true } },
          header: token ? { Authorization: `Bearer ${token}` } : {},
          timeout: CONFIG.REQUEST_TIMEOUT,
        })
        if (res.statusCode === 200) {
          this.pollResult(res.data.task_id)
        } else if (res.statusCode === 401) {
          uni.showToast({ title: "请先登录", icon: "none" })
          uni.navigateTo({ url: "/pages/index/index" })
        } else {
          uni.showToast({ title: "检测失败", icon: "error" })
          this.detecting = false
        }
      } catch (e) {
        uni.showToast({ title: "网络异常", icon: "error" })
        this.detecting = false
      }
    },
    async pollResult(taskId) {
      const token = uni.getStorageSync("access_token")
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 1000))
        try {
          const [err, res] = await uni.request({
            url: `${CONFIG.API_BASE}/detect/result/${taskId}`,
            header: token ? { Authorization: `Bearer ${token}` } : {},
          })
          if (res.statusCode === 200) { this.result = res.data; this.detecting = false; return }
        } catch (e) {
          // 继续轮询
        }
      }
      uni.showToast({ title: "检测超时，请稍后查看历史", icon: "none" })
      this.detecting = false
    }
  }
}
</script>

<style scoped>
.container { padding: 24rpx; }
textarea { width: 100%; padding: 16rpx; border: 1px solid #e2e8f0; border-radius: 8rpx; font-size: 28rpx; }
.result-card { margin-top: 24rpx; padding: 24rpx; background: white; border-radius: 12rpx; }
.verdict { font-size: 32rpx; font-weight: bold; text-align: center; }
.verdict.ai { color: #e53e3e; }
.verdict.human { color: #38a169; }
.confidence { text-align: center; margin-top: 12rpx; font-size: 28rpx; color: #4a5568; }
.risk { text-align: center; margin-top: 8rpx; font-size: 24rpx; color: #718096; }
.warning { margin-top: 12rpx; padding: 12rpx; background: #fffff0; color: #c05621; font-size: 24rpx; border-radius: 8rpx; }
</style>
