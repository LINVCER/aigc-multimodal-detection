<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
onMounted(() => auth.restore())
</script>

<template>
  <router-view />
</template>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #111827;
  background: #f3f4f6;
}
</style>
