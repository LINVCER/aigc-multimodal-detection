<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="page">
    <div class="wrap">
      <div class="code">404</div>
      <div class="title">页面不见了</div>
      <div class="desc">请检查地址或返回首页</div>
      <el-button type="primary" round size="large" style="margin-top: 32px" @click="router.push('/dashboard')">
        回到首页
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: var(--system-grouped-background);
}
.wrap { text-align: center; padding: 24px; }
.code {
  font-size: 120px;
  font-weight: var(--fw-bold);
  letter-spacing: -4px;
  color: var(--system-blue);
  line-height: 1;
}
.title { font-size: 28px; font-weight: var(--fw-semibold); letter-spacing: -0.5px; margin-top: 16px; }
.desc  { font-size: var(--fs-subhead); color: var(--label-secondary); margin-top: 8px; }
</style>
