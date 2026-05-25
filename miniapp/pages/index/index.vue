<template>
  <view class="container">
    <view class="header">
      <text class="title">AIGC--多模态检测</text>
      <text class="subtitle">多模态内容鉴伪平台</text>
    </view>

    <view class="grid">
      <view class="card" @click="navigateTo('/pages/text-detect/text-detect')">
        <text class="card-icon">T</text>
        <text class="card-title">文本检测</text>
        <text class="card-desc">识别 AI 生成文本</text>
      </view>
      <view class="card" @click="navigateTo('/pages/image-detect/image-detect')">
        <text class="card-icon">I</text>
        <text class="card-title">图像检测</text>
        <text class="card-desc">检测伪造图像</text>
      </view>
      <view class="card" @click="navigateTo('/pages/audio-detect/audio-detect')">
        <text class="card-icon">A</text>
        <text class="card-title">音频检测</text>
        <text class="card-desc">识别合成语音</text>
      </view>
      <view class="card" @click="navigateTo('/pages/history/history')">
        <text class="card-icon">H</text>
        <text class="card-title">检测历史</text>
        <text class="card-desc">查看过往记录</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  methods: {
    navigateTo(path) {
      uni.navigateTo({ url: path })
    }
  }
}
</script>

<style scoped>
.container { padding: 24rpx; }
.header { text-align: center; padding: 40rpx 0; }
.title { font-size: 48rpx; font-weight: bold; color: #1a1a2e; }
.subtitle { display: block; font-size: 24rpx; color: #718096; margin-top: 8rpx; }
.grid { display: flex; flex-wrap: wrap; gap: 20rpx; }
.card { width: calc(50% - 10rpx); background: white; border-radius: 16rpx; padding: 40rpx 20rpx; text-align: center; box-shadow: 0 4rpx 12rpx rgba(0,0,0,0.06); }
.card-icon { font-size: 48rpx; font-weight: bold; color: #409EFF; }
.card-title { display: block; font-size: 28rpx; font-weight: bold; margin-top: 16rpx; }
.card-desc { display: block; font-size: 22rpx; color: #a0aec0; margin-top: 8rpx; }
</style>
