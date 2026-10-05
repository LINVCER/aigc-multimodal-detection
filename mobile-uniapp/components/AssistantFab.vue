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
    <image class="fab-img" src="/static/ai_tag.png" mode="widthFix" />
  </view>
</template>

<style lang="scss" scoped>
.fab {
  position: fixed;
  right: $sp-4;
  z-index: $z-sticky;
  &--hover { opacity: 0.85; transform: scale(0.97); }
}
.fab-img {
  display: block;
  width: 186rpx;
}
</style>
