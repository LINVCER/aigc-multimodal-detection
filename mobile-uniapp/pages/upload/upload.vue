<script setup>
import { onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import { SCENARIO_MAP } from '@/utils/constants'

/* Wave 3.2 · 微信分享（上传页作为拉新第一入口） */
onShareAppMessage(() => ({
  title: '论文 / 音频 / 图像 AI 率检测 · 场景阈值一目了然',
  path: '/pages/upload/upload',
}))
onShareTimeline(() => ({
  title: '论文 / 音频 / 图像 AI 率检测',
}))

// 二级模态选择页 · A 方案：tabBar 「上传」→ 3 模态 tile → 三级详情
// 首页 quick-tile 可直连三级页跳过本页
const MODALITIES = [
  {
    key: 'text',
    label: '论文检测',
    desc: 'PDF / Word / TXT 或粘贴文本',
    scenarios: ['本科', '硕士', '博士', '职业', '自媒体'],
    accent: SCENARIO_MAP.academic_master.tint,
    wash: SCENARIO_MAP.academic_master.wash,
    ready: true,
    path: '/pages/upload/text',
  },
  {
    key: 'audio',
    label: '音频检测',
    desc: 'MP3 / WAV / M4A · 段级 AI 语音判定',
    scenarios: ['真人 vs TTS', '克隆音色'],
    accent: SCENARIO_MAP.self_media.tint,
    wash: SCENARIO_MAP.self_media.wash,
    ready: true,
    path: '/pages/upload/audio',
  },
  {
    key: 'image',
    label: '图像检测',
    desc: 'JPG / PNG · AI 生成图识别',
    scenarios: ['SD 系列', 'MJ / DALL·E'],
    accent: SCENARIO_MAP.academic_phd.tint,
    wash: SCENARIO_MAP.academic_phd.wash,
    ready: false,
    path: '/pages/upload/image',
  },
]

function pick(m) {
  if (!m.ready) {
    uni.showToast({ title: '图像检测 Wave 5 上线', icon: 'none' })
  }
  uni.navigateTo({ url: m.path })
}
</script>

<template>
  <view class="page">
    <!-- Large Title -->
    <view class="hero-header">
      <text class="large-title">选择检测方式</text>
      <text class="hero-sub">按你要检测的内容类型进入对应流程</text>
    </view>

    <!-- 三模态 tile -->
    <view class="modality-list">
      <view
        v-for="m in MODALITIES" :key="m.key"
        class="modality-tile"
        :class="{ disabled: !m.ready }"
        :style="{ background: m.wash }"
        hover-class="modality-tile-hover"
        @click="pick(m)"
      >
        <view class="tile-icon" :style="{ background: m.accent }">
          <text class="tile-icon-letter">{{ m.label.charAt(0) }}</text>
        </view>
        <view class="tile-body">
          <view class="tile-title-line">
            <text class="tile-title" :style="{ color: m.accent }">{{ m.label }}</text>
            <text v-if="!m.ready" class="tile-badge">建设中</text>
          </view>
          <text class="tile-desc">{{ m.desc }}</text>
          <view class="tile-tags">
            <text
              v-for="s in m.scenarios" :key="s"
              class="tile-tag"
              :style="{ color: m.accent, borderColor: m.accent + '55' }"
            >{{ s }}</text>
          </view>
        </view>
        <text class="tile-arrow" :style="{ color: m.accent }">›</text>
      </view>
    </view>

    <text class="privacy">
      论文原文加密存储，30 天后自动删除；报告保留 3 年
    </text>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

/* ---------- Large Title Hero ---------- */
.hero-header { padding: $sp-3 $sp-1 $sp-5; }
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

/* ---------- 模态 tile ---------- */
.modality-list {
  display: flex; flex-direction: column;
  gap: $sp-3;
}
.modality-tile {
  padding: $sp-4;
  border-radius: $radius-card;
  display: flex; align-items: center;
  transition: transform $duration-fast $ease-standard;
  box-shadow: $shadow-card;
  &.disabled { opacity: 0.72; }
}
.modality-tile-hover { transform: scale(0.98); }

.tile-icon {
  width: 96rpx; height: 96rpx;
  border-radius: $radius-lg;
  display: flex; align-items: center; justify-content: center;
  margin-right: $sp-4;
  flex-shrink: 0;
}
.tile-icon-letter {
  color: #FFFFFF;
  font-size: 48rpx;
  font-weight: $fw-bold;
  letter-spacing: $tracking-tight;
}

.tile-body { flex: 1; min-width: 0; }
.tile-title-line { display: flex; align-items: center; gap: $sp-2; }
.tile-title {
  font-size: $fs-title-3;
  font-weight: $fw-semibold;
  letter-spacing: $tracking-snug;
}
.tile-badge {
  font-size: $fs-caption-2;
  color: $label-secondary;
  background: $fill-tertiary;
  padding: 2rpx $sp-1;
  border-radius: $radius-pill;
  font-weight: $fw-medium;
}
.tile-desc {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-top: 6rpx;
  line-height: $lh-normal;
}
.tile-tags {
  margin-top: $sp-2;
  display: flex; flex-wrap: wrap; gap: 8rpx;
}
.tile-tag {
  font-size: $fs-caption-2;
  padding: 2rpx 12rpx;
  border-radius: $radius-pill;
  border: 1rpx solid;
  font-weight: $fw-medium;
}
.tile-arrow {
  font-size: 44rpx;
  line-height: 1;
  margin-left: $sp-2;
}

.privacy {
  display: block;
  margin-top: $sp-6;
  font-size: $fs-caption-1;
  color: $label-secondary;
  text-align: center;
  line-height: $lh-normal;
  padding: 0 $sp-5;
}
</style>
