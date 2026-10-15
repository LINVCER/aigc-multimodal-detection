<script setup>
import ZyIcon from '@/components/ZyIcon.vue'
// xiaobai=true 用小白形象（mood 为表情位），否则用 ZyIcon
defineProps({
  icon:       { type: String, default: 'file-text' },   // ZyIcon 名称
  xiaobai:    { type: Boolean, default: false },
  mood:       { type: String, default: 'shrug' },       // shrug | yawn | heart | cover | fist | think
  title:      { type: String, default: '这里还空着' },
  desc:       { type: String, default: '' },
  actionText: { type: String, default: '' },
})
const emit = defineEmits(['action'])
const MOOD_SRC = {
  shrug: '/static/xiaobai.png', yawn: '/static/xiaobai.gif', heart: '/static/xiaobai.png',
  cover: '/static/xiaobai.png', fist: '/static/xiaobai.png', think: '/static/xiaobai.gif',
}
</script>

<template>
  <view class="empty">
    <image v-if="xiaobai" class="xb" :src="MOOD_SRC[mood] || MOOD_SRC.shrug" mode="aspectFit" />
    <view v-else class="icon-wrap"><ZyIcon :name="icon" :size="64" color="#0F766E" /></view>
    <text class="title">{{ title }}</text>
    <text v-if="desc" class="desc">{{ desc }}</text>
    <button v-if="actionText" class="action" @click="emit('action')">{{ actionText }}</button>
  </view>
</template>

<style lang="scss" scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 160rpx 80rpx 80rpx;
}
.xb { width: 192rpx; height: 192rpx; margin-bottom: $sp-4; }
.icon-wrap {
  width: 128rpx; height: 128rpx; border-radius: 50%;
  background: $brand-primary-wash;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: $sp-4;
}
.title { font-size: $fs-title-3; font-weight: $fw-semibold; color: $label-primary; letter-spacing: $tracking-tight; }
.desc  {
  font-size: $fs-subhead; color: $label-secondary;
  margin-top: $sp-2; text-align: center; line-height: $lh-normal;
}
.action {
  margin-top: $sp-6;
  min-width: 300rpx;
  height: $size-btn-h-lg;
  line-height: $size-btn-h-lg;
  padding: 0 $sp-6;
  background: $brand-primary;
  color: #fff;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  border-radius: $radius-pill;
  transition: transform $duration-fast $ease-spring;
  &::after { border: none; }
  &:active { transform: scale(0.97); }
}
</style>
