<script setup>
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
    <image class="fab-img" src="/static/xiaobai.gif" mode="widthFix" />
  </view>
</template>

<style lang="scss" scoped>
.fab {
  position: fixed;
  right: $sp-4;
  z-index: $z-sticky;
  filter: drop-shadow(0 12rpx 28rpx rgba(15, 118, 110, 0.22));
  animation: breathe 3s ease-in-out infinite;
  &--hover { opacity: 0.85; transform: scale(0.97); animation: none; }
}
.fab-img {
  display: block;
  width: 186rpx;
}
/* 小白呼吸：空闲时才感知得到 */
@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}
@media (prefers-reduced-motion: reduce) {
  .fab { animation: none; }
}
</style>
