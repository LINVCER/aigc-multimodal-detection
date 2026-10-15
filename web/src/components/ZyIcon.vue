<script setup lang="ts">
import { computed } from 'vue'
import { ICONS, SPARK, NO_SPARK } from './icons/sparkline'

const props = withDefaults(defineProps<{ name: string; size?: number | string }>(), { size: 16 })
const body = computed(() => (ICONS[props.name] || ICONS.alert) + (NO_SPARK.has(props.name) ? '' : SPARK))
const px = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
</script>

<template>
  <svg
    class="zy-icon" :style="{ width: px, height: px }" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true" v-html="body"
  />
</template>

<style scoped>
.zy-icon { display: inline-block; flex: none; }
</style>
