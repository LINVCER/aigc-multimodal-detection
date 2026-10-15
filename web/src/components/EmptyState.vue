<script setup lang="ts">
import ZyIcon from '@/components/ZyIcon.vue'

// xiaobai=true 用小白形象（mood 为表情位），否则用 ZyIcon
withDefaults(defineProps<{
  icon?: string
  xiaobai?: boolean
  mood?: 'shrug' | 'yawn' | 'heart' | 'cover' | 'fist' | 'think'
  title: string
  desc?: string
  actionText?: string
}>(), { icon: 'file-text', xiaobai: false, mood: 'shrug' })
defineEmits<{ (e: 'action'): void }>()

const MOOD_SRC: Record<string, string> = {
  shrug: '/xiaobai.png', yawn: '/xiaobai.gif', heart: '/xiaobai.png', cover: '/xiaobai.png', fist: '/xiaobai.png', think: '/xiaobai.gif',
}
</script>

<template>
  <div class="empty">
    <img v-if="xiaobai" class="xb" :src="MOOD_SRC[mood] || MOOD_SRC.shrug" alt="" width="96" height="96" />
    <div v-else class="icon-wrap"><ZyIcon :name="icon" :size="30" /></div>
    <div class="title">{{ title }}</div>
    <div v-if="desc" class="desc">{{ desc }}</div>
    <el-button
      v-if="actionText"
      type="primary" size="large"
      style="margin-top: 28px; min-width: 180px"
      @click="$emit('action')"
    >{{ actionText }}</el-button>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 32px 48px;
}
.xb { width: 96px; height: 96px; margin-bottom: 16px; filter: drop-shadow(0 10px 18px rgba(15, 118, 110, 0.18)); }
.icon-wrap { width: 64px; height: 64px; border-radius: 50%; background: var(--ai-100); color: var(--ai-700); display: grid; place-items: center; margin-bottom: 16px; }
.title { font-size: var(--fs-title-3); font-weight: var(--fw-semibold); letter-spacing: -0.3px; color: var(--label); }
.desc  {
  font-size: var(--fs-subhead);
  color: var(--label-secondary);
  margin-top: 8px;
  text-align: center;
  line-height: 1.5;
}
</style>
