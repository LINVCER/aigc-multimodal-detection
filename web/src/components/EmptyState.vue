<script setup lang="ts">
defineProps<{
  icon?: string
  title: string
  desc?: string
  actionText?: string
}>()
defineEmits<{ (e: 'action'): void }>()
</script>

<template>
  <div class="empty">
    <div class="icon">{{ icon ?? '📭' }}</div>
    <div class="title">{{ title }}</div>
    <div v-if="desc" class="desc">{{ desc }}</div>
    <el-button
      v-if="actionText"
      type="primary" round size="large"
      style="margin-top: 32px; min-width: 200px"
      @click="$emit('action')"
    >{{ actionText }}</el-button>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 96px 32px 48px;
}
.icon  { font-size: 64px; opacity: 0.35; margin-bottom: 20px; }
.title { font-size: var(--fs-title-3); font-weight: var(--fw-semibold); letter-spacing: -0.3px; color: var(--label); }
.desc  {
  font-size: var(--fs-subhead);
  color: var(--label-secondary);
  margin-top: 8px;
  text-align: center;
  line-height: 1.5;
}
</style>
