<script setup lang="ts">
withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })
</script>

<template>
  <div class="skeleton">
    <div v-for="i in rows" :key="i" class="card">
      <div class="line line-title"></div>
      <div class="line line-meta"></div>
    </div>
  </div>
</template>

<style scoped>
.skeleton { padding: 16px 0; }
.card {
  background: var(--system-background);
  border-radius: var(--radius-card);
  padding: 20px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-card);
}
.line {
  height: 14px;
  border-radius: 7px;
  background: linear-gradient(90deg,
    rgba(60, 60, 67, 0.06) 0%,
    rgba(60, 60, 67, 0.14) 50%,
    rgba(60, 60, 67, 0.06) 100%);
  background-size: 200% 100%;
  animation: shimmer 1.6s var(--ease-standard) infinite;
}
.line-title { width: 70%; margin-bottom: 12px; }
.line-meta  { width: 40%; height: 12px; }
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
