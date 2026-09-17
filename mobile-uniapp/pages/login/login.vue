<script setup>
import { ref } from 'vue'
import { useAuth } from '@/store/auth'

const auth = useAuth()
const username = ref('')
const password = ref('')

async function onSubmit() {
  if (!username.value || !password.value) {
    uni.showToast({ title: '请输入账号和密码', icon: 'none' })
    return
  }
  try {
    await auth.login(username.value, password.value)
    uni.reLaunch({ url: '/pages/index/index' })
  } catch (e) {
    uni.showToast({ title: e?.message || '登录失败', icon: 'none' })
  }
}
</script>

<template>
  <view class="container">
    <view class="header">
      <text class="title">论文 AIGC 检测</text>
      <text class="subtitle">教育部 2026 新规 · 学位论文 AI 率检测</text>
    </view>

    <view class="form">
      <input class="input" v-model="username" placeholder="学号 / 工号" />
      <input class="input" v-model="password" placeholder="密码" password />
      <button class="submit" :loading="auth.loading" @click="onSubmit">登 录</button>
      <text class="hint">首次使用请通过学校统一身份认证或联系管理员开通</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.container {
  min-height: 100vh;
  padding: 120rpx 64rpx 60rpx;
  background: #fff;
}

.header {
  text-align: center;
  margin-bottom: 80rpx;
}
.title {
  display: block;
  font-size: 44rpx;
  font-weight: 700;
  color: #1a56db;
}
.subtitle {
  display: block;
  margin-top: 16rpx;
  font-size: 24rpx;
  color: #6b7280;
}

.input {
  height: 88rpx;
  border: 1rpx solid #d1d5db;
  border-radius: 16rpx;
  padding: 0 28rpx;
  font-size: 30rpx;
  margin-bottom: 28rpx;
}

.submit {
  background: #1a56db;
  color: #fff;
  font-size: 32rpx;
  font-weight: 600;
  border-radius: 16rpx;
  margin-top: 16rpx;
}

.hint {
  display: block;
  margin-top: 40rpx;
  font-size: 22rpx;
  color: #9ca3af;
  text-align: center;
}
</style>
