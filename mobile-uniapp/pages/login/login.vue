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
    uni.reLaunch({ url: '/pages/home/home' })
  } catch (e) {
    uni.showToast({ title: e?.message || '登录失败', icon: 'none' })
  }
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="brand">论文AIGC检测</text>
      <text class="tagline">教育部 2026 新规 · 学位论文 AI 率检测</text>
    </view>

    <view class="form">
      <view class="field">
        <input v-model="username" class="input" placeholder="学号 / 工号" placeholder-style="color: rgba(60,60,67,0.30)" />
      </view>
      <view class="field">
        <input v-model="password" class="input" placeholder="密码" password placeholder-style="color: rgba(60,60,67,0.30)" />
      </view>

      <button class="submit" :loading="auth.loading" @click="onSubmit">登 录</button>
      <text class="footer-hint">首次使用请通过学校统一身份认证</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #FFFFFF;
  padding: 200rpx 64rpx 60rpx;
}

/* Hero 大标题 */
.hero { margin-bottom: 120rpx; }
.brand {
  display: block;
  font-size: 68rpx;
  font-weight: 700;
  letter-spacing: -1rpx;
  color: #000;
  line-height: 1.1;
}
.tagline {
  display: block;
  font-size: 30rpx;
  color: rgba(60,60,67,0.60);
  margin-top: 20rpx;
}

/* Inset Grouped 输入框 */
.form {}
.field {
  background: #F2F2F7;
  border-radius: 28rpx;
  padding: 4rpx 32rpx;
  margin-bottom: 20rpx;
}
.input {
  height: 96rpx;
  font-size: 34rpx;
  color: #000;
}

/* 主按钮：填充药丸 */
.submit {
  margin-top: 40rpx;
  height: 100rpx;
  line-height: 100rpx;
  background: #007AFF;
  color: #FFFFFF;
  font-size: 34rpx;
  font-weight: 600;
  border-radius: 9999rpx;
  letter-spacing: 2rpx;
  transition: transform 200ms cubic-bezier(0.32, 0.72, 0, 1),
              opacity 200ms;
}
.submit[loading], .submit:active { transform: scale(0.98); opacity: 0.88; }

.footer-hint {
  display: block;
  margin-top: 48rpx;
  font-size: 24rpx;
  color: rgba(60,60,67,0.60);
  text-align: center;
}
</style>
