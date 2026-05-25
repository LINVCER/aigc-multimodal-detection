<template>
  <view class="container">
    <view v-if="loading" class="loading">
      <text class="loading-text">检测中...</text>
      <text class="loading-hint">请耐心等待，正在分析内容</text>
    </view>

    <view v-else-if="result" class="result-card">
      <view class="verdict" :class="result.is_ai_generated ? 'ai' : 'human'">
        {{ result.is_ai_generated ? '疑似 AI 生成' : '可能人类写作/真实' }}
      </view>

      <view class="confidence-bar">
        <view class="confidence-label">AI 置信度</view>
        <view class="confidence-value">{{ (result.confidence * 100).toFixed(1) }}%</view>
        <view class="bar-track">
          <view class="bar-fill" :style="{ width: (result.confidence * 100) + '%' }"
                :class="result.is_ai_generated ? 'fill-ai' : 'fill-human'"></view>
        </view>
      </view>

      <view v-if="result.calibrated_confidence" class="info-row">
        <text class="info-label">校准置信度</text>
        <text class="info-value">{{ (result.calibrated_confidence * 100).toFixed(1) }}%</text>
      </view>

      <view v-if="result.risk_level" class="info-row">
        <text class="info-label">风险等级</text>
        <text class="info-value risk-tag" :class="'risk-' + result.risk_level">
          {{ { low: '低风险', medium: '中风险', high: '高风险' }[result.risk_level] }}
        </text>
      </view>

      <view v-if="result.arbitration_warning" class="warning">
        {{ result.arbitration_warning }}
      </view>

      <view v-if="result.model_attribution && result.model_attribution.length" class="attribution">
        <view class="section-title">模型溯源</view>
        <view v-for="attr in result.model_attribution" :key="attr.model" class="attr-item">
          <text>{{ attr.model }}</text>
          <text class="attr-score">{{ (attr.score * 100).toFixed(0) }}%</text>
        </view>
      </view>
    </view>

    <view v-else class="error">
      <text>暂无检测结果</text>
    </view>
  </view>
</template>

<script>
import CONFIG from "../config.js"

export default {
  data() {
    return {
      taskId: "",
      modality: "text",
      result: null,
      loading: true,
    }
  },
  onLoad(options) {
    if (options.taskId) {
      this.taskId = options.taskId
      this.modality = options.modality || "text"
      this.pollResult()
    }
  },
  methods: {
    async pollResult() {
      const token = uni.getStorageSync("access_token")
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 1000))
        try {
          const [err, res] = await uni.request({
            url: `${CONFIG.API_BASE}/detect/result/${this.taskId}`,
            header: token ? { Authorization: `Bearer ${token}` } : {},
          })
          if (res.statusCode === 200) {
            this.result = res.data
            this.loading = false
            return
          }
        } catch (e) { /* 继续等待 */ }
      }
      this.loading = false
      uni.showToast({ title: "获取结果超时", icon: "none" })
    }
  }
}
</script>

<style scoped>
.container { padding: 24rpx; }
.loading { text-align: center; padding: 120rpx 0; }
.loading-text { font-size: 36rpx; color: #409EFF; }
.loading-hint { display: block; font-size: 24rpx; color: #a0aec0; margin-top: 16rpx; }
.result-card { background: white; border-radius: 16rpx; padding: 32rpx 24rpx; box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.06); }
.verdict { font-size: 40rpx; font-weight: bold; text-align: center; padding: 16rpx 0; }
.verdict.ai { color: #e53e3e; }
.verdict.human { color: #38a169; }
.confidence-bar { margin-top: 24rpx; }
.confidence-label { font-size: 24rpx; color: #718096; }
.confidence-value { font-size: 48rpx; font-weight: bold; text-align: center; color: #2d3748; margin: 8rpx 0; }
.bar-track { height: 16rpx; background: #e2e8f0; border-radius: 8rpx; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 8rpx; transition: width 0.5s; }
.fill-ai { background: linear-gradient(90deg, #fc8181, #e53e3e); }
.fill-human { background: linear-gradient(90deg, #68d391, #38a169); }
.info-row { display: flex; justify-content: space-between; align-items: center; padding: 16rpx 0; border-bottom: 1rpx solid #f0f0f0; }
.info-label { font-size: 26rpx; color: #718096; }
.info-value { font-size: 26rpx; color: #2d3748; font-weight: bold; }
.risk-tag { padding: 4rpx 16rpx; border-radius: 20rpx; color: white; font-size: 22rpx; }
.risk-low { background: #38a169; }
.risk-medium { background: #d69e2e; }
.risk-high { background: #e53e3e; }
.warning { margin-top: 16rpx; padding: 16rpx; background: #fffff0; border: 1rpx solid #f6e05e; border-radius: 8rpx; color: #c05621; font-size: 24rpx; }
.attribution { margin-top: 20rpx; }
.section-title { font-size: 28rpx; font-weight: bold; color: #2d3748; margin-bottom: 12rpx; }
.attr-item { display: flex; justify-content: space-between; padding: 8rpx 0; font-size: 24rpx; color: #4a5568; }
.attr-score { color: #409EFF; font-weight: bold; }
.error { text-align: center; padding: 120rpx 0; color: #a0aec0; }
</style>
