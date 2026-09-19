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

/**
 * 微信一键登录（Wave 3.1）
 * 流程：wx.login → code → POST /api/v1/auth/wechat/login
 * 昵称/头像可选（首次登录用户可通过 wx.getUserProfile 补齐，本轮先透传空）
 */
async function onWechatLogin() {
  uni.login({
    provider: 'weixin',
    success: async (res) => {
      if (!res.code) {
        uni.showToast({ title: '未拿到微信 code', icon: 'none' })
        return
      }
      try {
        await auth.loginByWechat({ code: res.code })
        uni.reLaunch({ url: '/pages/home/home' })
      } catch (e) {
        uni.showToast({ title: e?.message || '微信登录失败', icon: 'none' })
      }
    },
    fail: () => uni.showToast({ title: '微信授权失败', icon: 'none' }),
  })
}
</script>

<template>
  <view class="page">
    <view class="hero">
      <text class="brand">论文AIGC检测</text>
      <text class="tagline">AI 率 · 段落热力 · 疑似来源分布</text>
    </view>

    <view class="form">
      <view class="field">
        <input v-model="username" class="input" placeholder="账号 / 手机号" placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" />
      </view>
      <view class="field">
        <input v-model="password" class="input" placeholder="密码" password placeholder-style="color: rgba(60,60,67,0.30)" :cursor-spacing="24" :adjust-position="true" />
      </view>

      <button class="submit" :loading="auth.loading" @click="onSubmit">登 录</button>

      <!-- 微信一键登录 · 仅小程序端可见（H5 不支持 uni.login provider=weixin）-->
      <!-- #ifdef MP-WEIXIN -->
      <view class="divider"><text class="divider-text">或</text></view>
      <button class="wechat-btn" @click="onWechatLogin">
        <view class="wechat-icon" />
        <text class="wechat-text">微信一键登录</text>
      </button>
      <!-- #endif -->

      <text class="footer-hint">未注册账号将自动创建 · 登录即表示同意隐私政策</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: $bg-primary;
  padding: 200rpx $sp-8 60rpx;
}

/* Hero 大标题 */
.hero { margin-bottom: 120rpx; }
.brand {
  display: block;
  font-size: $fs-large-title;
  font-weight: $fw-bold;
  letter-spacing: $tracking-tight;
  color: $label-primary;
  line-height: $lh-tight;
}
.tagline {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-top: $sp-3;
}

/* Inset Grouped 输入框 */
.field {
  background: $bg-grouped-primary;
  border-radius: $radius-card;
  padding: 4rpx $sp-4;
  margin-bottom: $sp-3;
}
.input {
  height: $size-input-h;
  font-size: $fs-body;
  color: $label-primary;
}

/* 主按钮：填充药丸 */
.submit {
  margin-top: $sp-5;
  height: $size-btn-h-lg;
  line-height: $size-btn-h-lg;
  background: $brand-primary;
  color: #FFFFFF;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  border-radius: $radius-pill;
  letter-spacing: 2rpx;
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;
  &:active { transform: scale(#{$tap-scale}); opacity: 0.88; }
}

/* 分割线 · 或 */
.divider {
  display: flex; align-items: center; justify-content: center;
  margin: $sp-5 0 $sp-3;
  position: relative;
  &::before, &::after {
    content: '';
    flex: 1;
    height: $stroke-hairline;
    background: $separator;
  }
}
.divider-text {
  padding: 0 $sp-3;
  font-size: $fs-caption-1;
  color: $label-secondary;
}

/* 微信按钮 · 微信绿 · icon 圆角方块内 W 字 */
.wechat-btn {
  height: $size-btn-h-lg;
  line-height: $size-btn-h-lg;
  background: #07C160;    // 微信官方绿
  color: #FFFFFF;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  border-radius: $radius-pill;
  display: flex; align-items: center; justify-content: center;
  gap: $sp-2;
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;
  &:active { transform: scale(#{$tap-scale}); opacity: 0.88; }
}
.wechat-icon {
  width: 40rpx; height: 40rpx;
  background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23FFFFFF'><path d='M9.5 4C5.4 4 2 6.6 2 10c0 1.8 1 3.5 2.6 4.6L4 17l2.7-1.4c.9.2 1.8.3 2.8.3.3 0 .6 0 .9-.1-.2-.6-.4-1.3-.4-2 0-3.3 3.3-6 7.5-6 .3 0 .6 0 .9.1C17.7 5.6 13.9 4 9.5 4zm-3 3.6c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm5.5 0c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1z'/><path d='M22 14c0-2.8-2.9-5-6.5-5S9 11.2 9 14s2.9 5 6.5 5c.8 0 1.6-.1 2.3-.3l2 1-.5-2C21 16.7 22 15.4 22 14zm-9-1.4c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.4-.8.8-.8zm4.5 0c.4 0 .8.3.8.8 0 .4-.3.8-.8.8-.4 0-.8-.3-.8-.8 0-.4.3-.8.8-.8z'/></svg>") no-repeat center / contain;
}

.footer-hint {
  display: block;
  margin-top: $sp-6;
  font-size: $fs-caption-1;
  color: $label-secondary;
  text-align: center;
  line-height: $lh-normal;
}
</style>
