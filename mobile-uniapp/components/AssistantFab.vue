<script setup>
/*
 * 论文检测助手 · 右下角悬浮入口
 * 挂在 4 个 tab 页；task/detail 用 hero 区按钮不用 FAB。
 * ENABLE_ASSISTANT=false 时整体不渲染（助手须等新 checkpoint 上线后再对用户开放）。
 */
const ENABLE_ASSISTANT = true

const props = defineProps({
  taskId: { type: Number, default: 0 },
  /** tab 页底部有 tabBar，FAB 需要抬高 */
  bottom: { type: String, default: '160rpx' },
})

function open() {
  const url = props.taskId ? `/pages/assistant/chat?taskId=${props.taskId}` : '/pages/assistant/chat'
  uni.navigateTo({ url })
}
</script>

<template>
  <view v-if="ENABLE_ASSISTANT" class="fab" :style="{ bottom }" hover-class="fab--hover" @click="open">
    <text class="fab-icon">AI</text>
    <text class="fab-label">问助手</text>
  </view>
</template>

<style lang="scss" scoped>
.fab {
  position: fixed;
  right: $sp-4;
  z-index: $z-sticky;
  display: flex; align-items: center; gap: $sp-1;
  padding: $sp-2 $sp-3 $sp-2 $sp-2;
  border-radius: $radius-pill;
  background: $brand-gradient-vivid; color: #fff;
  box-shadow: $shadow-lift;
  &--hover { opacity: 0.85; transform: scale(0.97); }
}
.fab-icon {
  width: 52rpx; height: 52rpx; border-radius: $radius-pill;
  background: rgba(255, 255, 255, 0.22);
  font-size: $fs-caption-1; font-weight: $fw-bold;
  display: flex; align-items: center; justify-content: center;
}
.fab-label { font-size: $fs-footnote; font-weight: $fw-semibold; }
</style>
