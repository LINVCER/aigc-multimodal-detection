<script setup>
function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/upload/upload' })
}

function subscribe() {
  uni.showToast({ title: '收到，上线时通知你', icon: 'success' })
}
</script>

<template>
  <view class="page">
    <view class="back-bar" hover-class="back-bar-hover" @click="goBack">
      <text class="back-arrow">‹</text>
      <text class="back-text">检测方式</text>
    </view>

    <view class="hero-header">
      <text class="large-title">图像检测</text>
      <text class="hero-sub">AI 生成图识别 · SD / Midjourney / DALL·E</text>
    </view>

    <view class="empty-card">
      <view class="empty-icon">
        <view class="empty-icon-inner" />
      </view>
      <text class="empty-title">建设中</text>
      <text class="empty-desc">
        图像检测（含 GAN / Diffusion / 篡改判定）在 Wave 5 推进；
        当前 ml/training/image/ 骨架待训练，接入完成后本页即上线。
      </text>
      <button class="btn-tinted subscribe-btn" @click="subscribe">上线时通知我</button>
    </view>

    <text class="privacy">
      建议先用「论文检测」或「音频检测」体验完整流程
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

.empty-card {
  @include card;
  margin-top: $sp-4;
  padding: 80rpx $sp-5 $sp-5;
  display: flex; flex-direction: column; align-items: center;
}
.empty-icon {
  width: 140rpx; height: 140rpx;
  border-radius: 50%;
  background: $brand-primary-wash;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: $sp-4;
}
.empty-icon-inner {
  width: 60rpx; height: 60rpx;
  border-radius: $radius-sm;
  background: $brand-primary;
  transform: rotate(45deg);
  opacity: 0.72;
}
.empty-title {
  display: block;
  font-size: $fs-title-3;
  font-weight: $fw-semibold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
}
.empty-desc {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  line-height: $lh-relaxed;
  text-align: center;
  margin-top: $sp-2;
}

.btn-tinted { @include btn-secondary; }
.subscribe-btn {
  margin-top: $sp-5;
  width: 100%;
}

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
