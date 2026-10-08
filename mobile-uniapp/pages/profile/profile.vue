<script setup>
import { ref, computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'
import { getStatistics } from '@/api/detect'
import FeedbackSheet from '@/components/FeedbackSheet.vue'
import AssistantFab from '@/components/AssistantFab.vue'

const auth = useAuth()
const feedbackOpen = ref(false)
const pwdOpen = ref(false)
const pwd = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdError = computed(() => {
  const p = pwd.value
  if (!p.oldPassword) return '请输入原密码'
  if (p.newPassword.length < 6 || p.newPassword.length > 32) return '新密码长度 6-32 位'
  if (!/[A-Za-z]/.test(p.newPassword) || !/[0-9]/.test(p.newPassword)) return '新密码需同时包含字母和数字'
  if (p.newPassword === p.oldPassword) return '新密码不能与原密码相同'
  if (p.confirmPassword !== p.newPassword) return '两次输入的新密码不一致'
  return ''
})
function openPwd() { pwd.value = { oldPassword: '', newPassword: '', confirmPassword: '' }; pwdOpen.value = true }
async function submitPassword() {
  if (pwdError.value) { uni.showToast({ title: pwdError.value, icon: 'none' }); return }
  try {
    await auth.changePassword(pwd.value.oldPassword, pwd.value.newPassword, pwd.value.confirmPassword)
    pwdOpen.value = false
    uni.showToast({ title: '密码已修改，请重新登录', icon: 'none' })
    setTimeout(() => uni.reLaunch({ url: '/pages/login/login' }), 800)
  } catch (e) { /* request 已 toast */ }
}
const stats = ref(null)   // { total, avgAiRate, passRate, done, thisMonth, today }

const avatarLetter = computed(() => (auth.username || 'U')[0].toUpperCase())
const roleText = computed(() =>
  auth.role === 'OPS_ADMIN' ? '运营团队 · 内部账号'
    : auth.role === 'ADMIN' ? '系统管理员'
    : '个人版 · AI 检测'
)

// Wave 4.4 · 版本号动态读：
//   1) 优先 vite 编译期 env 注入的 VITE_APP_VERSION（部署方便统一改）
//   2) 兜底小程序 uni.getAccountInfoSync().miniProgram.envVersion / manifest 硬写
//   3) 最终兜底常量（H5 无 miniProgram）
function readAppVersion() {
  // 裸写 import.meta.env.XXX 让 Vite build 时静态替换；带 typeof 探测会残留到
  // 小程序运行时触发 utils/url.js 隐式 polyfill require（Wave 4 收官修复）
  // eslint-disable-next-line
  const envVer = import.meta.env.VITE_APP_VERSION
  if (envVer) return String(envVer)
  try {
    // #ifdef MP-WEIXIN
    const acc = uni.getAccountInfoSync?.()
    if (acc?.miniProgram?.version) return acc.miniProgram.version
    // #endif
  } catch { /* ignore */ }
  return '0.2.0'
}
const appVersion = readAppVersion()

function logout() {
  uni.showModal({
    title: '退出登录',
    content: '确定要退出吗？',
    confirmColor: '#FF3B30',
    cancelColor: '#007AFF',
    success: (res) => { if (res.confirm) auth.logout() },
  })
}

function comingSoon(name) {
  uni.showToast({ title: `${name} 即将上线`, icon: 'none' })
}
function goMyFeedback() { uni.navigateTo({ url: '/pages/feedback/mine' }) }

function goPrivacy() { uni.navigateTo({ url: '/pages/about/privacy' }) }
function goVerify() { uni.navigateTo({ url: '/pages/verify/verify' }) }

function goHistory() { uni.switchTab({ url: '/pages/index/index' }) }

onShow(() => {
  getStatistics()
    .then((s) => { stats.value = s })
    .catch(() => { stats.value = null })
})
</script>

<template>
  <view class="page">
    <!-- 用户卡 -->
    <view class="user-card">
      <view class="avatar">
        <text>{{ avatarLetter }}</text>
      </view>
      <view class="user-info">
        <text class="user-name">{{ auth.username || '已登录用户' }}</text>
        <text class="user-role">{{ roleText }}</text>
      </view>
    </view>

    <!-- 检测统计 -->
    <view class="stats-card">
      <view class="stat">
        <text class="stat-num">{{ stats ? stats.total : '—' }}</text>
        <text class="stat-label">累计检测</text>
      </view>
      <view class="stat">
        <text class="stat-num">{{ stats ? stats.avgAiRate.toFixed(1) + '%' : '—' }}</text>
        <text class="stat-label">平均 AI 率</text>
      </view>
      <view class="stat">
        <text class="stat-num">{{ stats ? stats.passRate + '%' : '—' }}</text>
        <text class="stat-label">达标率</text>
      </view>
    </view>

    <!-- 账户 -->
    <text class="group-label">账户</text>
    <view class="group-card">
      <view class="row" hover-class="row-hover" @click="comingSoon('额度余额')">
        <text class="row-title">额度余额</text>
        <view class="row-tail">
          <text class="row-value muted">接入后展示</text>
          <text class="chevron">›</text>
        </view>
      </view>
      <view class="separator" />
      <view class="row" hover-class="row-hover" @click="goHistory">
        <text class="row-title">历史报告</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator" />
      <view class="row" hover-class="row-hover" @click="openPwd">
        <text class="row-title">修改密码</text>
        <text class="chevron">›</text>
      </view>
    </view>

    <!-- 反馈 -->
    <text class="group-label">反馈</text>
    <view class="group-card">
      <view class="row" hover-class="row-hover" @click="feedbackOpen = true">
        <text class="row-title">意见反馈</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator" />
      <view class="row" hover-class="row-hover" @click="goMyFeedback">
        <text class="row-title">我的反馈</text>
        <view class="row-tail">
          <text class="row-value muted">查看回复</text>
          <text class="chevron">›</text>
        </view>
      </view>
    </view>

    <!-- 关于 -->
    <text class="group-label">关于</text>
    <view class="group-card">
      <!-- Wave 3.4 · 联系客服 · 微信小程序原生 · H5/App 隐藏 -->
      <!-- #ifdef MP-WEIXIN -->
      <button class="row contact-row" open-type="contact" hover-class="row-hover">
        <text class="row-title">联系客服</text>
        <view class="row-tail">
          <text class="row-value muted">微信原生</text>
          <text class="chevron">›</text>
        </view>
      </button>
      <view class="separator" />
      <!-- #endif -->
      <view class="row" hover-class="row-hover" @click="goVerify">
        <text class="row-title">验证报告真伪</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator" />
      <view class="row" hover-class="row-hover" @click="goPrivacy">
        <text class="row-title">隐私政策</text>
        <text class="chevron">›</text>
      </view>
      <view class="separator" />
      <view class="row">
        <text class="row-title">版本</text>
        <text class="row-value muted">v{{ appVersion }}</text>
      </view>
    </view>

    <!-- 退出登录 -->
    <view class="danger-card" hover-class="danger-card-hover" @click="logout">
      <text class="danger-text">退出登录</text>
    </view>

    <FeedbackSheet v-model="feedbackOpen" default-category="suggestion" />

    <!-- 修改密码 -->
    <view v-if="pwdOpen" class="mask" @click="pwdOpen = false" />
    <view class="sheet" :class="{ open: pwdOpen }">
      <view class="sheet-head"><text class="sheet-title">修改密码</text><text class="sheet-close" @click="pwdOpen = false">✕</text></view>
      <view class="sheet-field"><input v-model="pwd.oldPassword" class="sheet-input" password placeholder="原密码" placeholder-style="color: rgba(60,60,67,0.30)" :adjust-position="true" :cursor-spacing="24" /></view>
      <view class="sheet-field"><input v-model="pwd.newPassword" class="sheet-input" password placeholder="新密码（6-32 位，含字母和数字）" placeholder-style="color: rgba(60,60,67,0.30)" :adjust-position="true" :cursor-spacing="24" /></view>
      <view class="sheet-field"><input v-model="pwd.confirmPassword" class="sheet-input" password placeholder="确认新密码" placeholder-style="color: rgba(60,60,67,0.30)" :adjust-position="true" :cursor-spacing="24" /></view>
      <text class="sheet-hint">{{ pwdError && (pwd.oldPassword || pwd.newPassword) ? pwdError : '修改成功后所有设备需重新登录' }}</text>
      <button class="sheet-submit" :class="{ disabled: !!pwdError }" :disabled="!!pwdError" :loading="auth.loading" @click="submitPassword">确认修改</button>
    </view>

    <!-- 论文检测助手入口 -->
    <AssistantFab />
  </view>
</template>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  padding: $sp-3 $sp-4 100rpx;
  background: $bg-grouped-primary;
}

/* 用户卡 · gradient avatar + 姓名 */
.user-card {
  @include card;
  padding: $sp-5 $sp-4;
  display: flex;
  align-items: center;
}
.avatar {
  width: $size-avatar-lg; height: $size-avatar-lg;
  border-radius: $radius-pill;
  background: $brand-gradient;
  color: #FFFFFF;
  font-size: 52rpx;
  font-weight: $fw-semibold;
  display: flex; align-items: center; justify-content: center;
  margin-right: $sp-4;
  flex-shrink: 0;
}
.user-info { flex: 1; min-width: 0; }
.user-name {
  display: block;
  font-size: $fs-title-3;
  font-weight: $fw-semibold;
  color: $label-primary;
  letter-spacing: $tracking-snug;
}
.user-role {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  margin-top: 8rpx;
}

/* 检测统计条 */
.stats-card {
  @include card;
  margin-top: $sp-3;
  padding: $sp-4;
  display: flex;
  justify-content: space-around;
}
.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat-num {
  font-size: $fs-title-3;
  font-weight: $fw-semibold;
  color: $label-primary;
}
.stat-label {
  font-size: $fs-caption-1;
  color: $label-secondary;
  margin-top: $sp-1;
}

/* Inset Grouped Section */
.group-label {
  @include group-label;
}
.group-card {
  @include card-flush;
}

/* Row（Inset Grouped 单行） */
.row {
  min-height: $size-row-h;
  padding: $sp-3 $sp-4;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: background $duration-fast $ease-standard;
}
/* button 元素默认背景/边框清理，让 open-type=contact 看起来跟 view.row 一致 */
.contact-row {
  background: transparent;
  border: none;
  border-radius: 0;
  width: 100%;
  text-align: left;
  color: $label-primary;
  font-size: $fs-body;
  &::after { border: none; }
}
.row-hover { background: rgba(60, 60, 67, 0.06); }
.row-title {
  font-size: $fs-body;
  color: $label-primary;
}
.row-tail {
  display: flex; align-items: center;
}
.row-value {
  font-size: $fs-subhead;
  color: $label-primary;
  margin-right: $sp-1;
  &.muted { color: $label-secondary; }
}
.chevron {
  color: $label-tertiary;
  font-size: $icon-md;
  line-height: 1;
  margin-left: $sp-1;
}
.separator {
  height: $stroke-hairline;
  background: $separator;
  margin-left: $sp-4;
}

/* 修改密码 sheet */
.mask { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.35); z-index: $z-sheet; }
.sheet {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: #{$z-sheet + 1};
  background: $bg-primary; border-radius: $radius-xl $radius-xl 0 0;
  padding: $sp-4 $sp-4 #{"calc(#{$sp-6} + env(safe-area-inset-bottom))"};
  transform: translateY(100%); transition: transform $duration-base $ease-standard;
  &.open { transform: translateY(0); }
}
.sheet-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: $sp-4; }
.sheet-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.sheet-close { font-size: $fs-headline; color: $label-tertiary; padding: $sp-1; }
.sheet-field { background: $bg-grouped-primary; border-radius: $radius-card; padding: 4rpx $sp-4; margin-bottom: $sp-3; }
.sheet-input { height: $size-input-h; font-size: $fs-body; color: $label-primary; }
.sheet-hint { display: block; font-size: $fs-caption-1; color: $label-tertiary; margin: 0 $sp-1 $sp-3; }
.sheet-submit {
  height: $size-btn-h-lg; line-height: $size-btn-h-lg; background: $brand-primary; color: #fff;
  font-size: $fs-headline; font-weight: $fw-semibold; border-radius: $radius-pill;
  &.disabled { opacity: 0.45; }
}

/* 危险卡 · 单独按钮式卡片 */
.danger-card {
  @include card-flush;
  margin-top: $sp-6;
  padding: $sp-4;
  text-align: center;
  transition: background $duration-fast $ease-standard;
}
.danger-card-hover { background: rgba(60, 60, 67, 0.06); }
.danger-text {
  font-size: $fs-headline;
  color: $danger-solid;
  font-weight: $fw-medium;
}
</style>
