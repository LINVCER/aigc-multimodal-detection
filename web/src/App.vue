<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
onMounted(() => {
  auth.restore()
  if (auth.token) auth.validate()
})
</script>

<template>
  <router-view />
</template>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
  font-family: var(--el-font-family);
  color: var(--label);
  background: var(--system-grouped-background);
}
</style>
