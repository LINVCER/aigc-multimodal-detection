<script setup>
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'

/* ---------- 网络状态兜底（Wave 4.2）---------- */
let netOfflineToastOn = false
function bindNetworkWatcher() {
  uni.onNetworkStatusChange((res) => {
    if (!res.isConnected && !netOfflineToastOn) {
      netOfflineToastOn = true
      uni.showToast({ title: '网络已断开', icon: 'none', duration: 2000 })
    } else if (res.isConnected && netOfflineToastOn) {
      netOfflineToastOn = false
      uni.showToast({ title: '网络已恢复', icon: 'success', duration: 1500 })
    }
  })
}

/* ---------- 深色模式（Wave 4.1 · 骨架）----------
 * 生产切换需将 uni.scss 里的语义 tokens 从 SCSS 变量重写为 CSS 变量（--xxx），
 * 页面走 var(--xxx)。当前 SCSS 变量编译时展开，运行时不可切换，只做检测骨架。
 * 见 docs/releases/v0.2.0/release-notes.md · Wave 4 备忘。
 */
function detectTheme() {
  const sys = uni.getSystemInfoSync()
  // H5 走 prefers-color-scheme；小程序端 pages.json 加 darkmode 后 sys.theme = 'dark' | 'light'
  const theme = sys.theme || (typeof matchMedia !== 'undefined'
    && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  uni.setStorageSync('sys_theme', theme)
  return theme
}

onLaunch(() => {
  const auth = useAuth()
  auth.restore()
  detectTheme()
  bindNetworkWatcher()
  if (!auth.token) {
    uni.reLaunch({ url: '/pages/login/login' })
  } else {
    auth.validate().then((ok) => { if (!ok) uni.reLaunch({ url: '/pages/login/login' }) })
  }
})
onShow(() => { /* 前台恢复时重探测（用户可能切换系统主题） */ detectTheme() })
onHide(() => { /* no-op */ })
</script>

<style lang="scss">
/* ========== 全局基础 · Apple 语义色板 + SF Pro 字栈 ========== */
page {
  background-color: $bg-grouped-primary;
  font-family: $font-family;
  color: $label-primary;
  font-size: $fs-body;
  line-height: $lh-normal;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
view, text, button, input { box-sizing: border-box; }

/* ========== H5 浏览器自动填充 ==========
 * Chrome 对自动填充过的 input 会强制加 #E8F0FE 蓝底 + 黑字，普通 background 覆盖不掉。
 * 组合拳：① background-clip:text 把底色裁进文字字形（框就没了）
 *        ② text-fill-color 固定字色 ③ 超长 transition 延迟底色上色。
 * 必须放全局样式：页面里的 scoped / 普通 <style> 都会被 uni 处理，命中不到内部 input。
 */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
input:-webkit-autofill:active {
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: $label-primary;
  caret-color: $label-primary;
  transition: background-color 9999s ease-in-out 0s, color 9999s ease-in-out 0s;
}

/* uni-app / 微信小程序默认按钮边框清除 */
button { border: none; }
button::after { border: none; }


/* ========== H5 端 tabBar 精修 · iOS 磨砂玻璃风 ========== */
/*
 * pages.json 里的 tabBar.color / selectedColor 决定字色 icon 色（跨端一致），
 * 这里追加 H5 端视觉层：磨砂背景、hairline 分割线、按压反馈、字号/字重。
 * 小程序端由原生渲染，不受此段影响。
 */

/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar {
  /* 磨砂玻璃 · H5 有效；小程序不支持时降级到实心白 */
  background: rgba(255, 255, 255, 0.82) !important;
  backdrop-filter: saturate(180%) blur(20rpx);
  -webkit-backdrop-filter: saturate(180%) blur(20rpx);

  /* iOS 顶部 hairline，取代 uni 默认粗边 */
  border-top: $stroke-hairline solid $separator !important;
  box-shadow: none !important;
}

/* 顶部原生边线隐藏（走上面 border-top 统一） */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar-border,
.uni-tabbar__border {
  display: none !important;
}

/* tab 项 · 按压反馈 + 过渡 */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar__item {
  transition: transform $duration-fast $ease-standard, opacity $duration-fast;

  &:active {
    transform: scale(0.94);
    opacity: 0.72;
  }
}

/* icon 尺寸 · icon 未配置时（当前是纯文字）保持简洁 */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar__icon {
  width: $icon-md !important;
  height: $icon-md !important;
  margin-bottom: 6rpx;
}

/* label 字号 & 字重 */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar__label {
  font-size: $fs-caption-2 !important;
  font-weight: $fw-medium;
  letter-spacing: 0.5rpx;
  line-height: 1.2;
  transition: font-weight $duration-fast $ease-standard;
}

/* 激活态 · 字重加粗 · 微下沉指示（与 iOS 系统 tabbar 一致的 subtle 反馈） */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar__item.uni-tabbar__item--active .uni-tabbar__label,
.uni-tabbar__item[data-selected="true"] .uni-tabbar__label {
  font-weight: $fw-semibold;
}

/* 无 icon 时（当前 pages.json 未配 iconPath），label 单独居中 · 加大点触区 */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar__label:only-child {
  font-size: $fs-footnote !important;
  padding: $sp-2 0;
}

/* iPhone 底部安全区 · 保证磨砂背景延展到 Home Indicator 区 */
/* stylelint-disable-next-line selector-class-pattern */
.uni-tabbar {
  padding-bottom: env(safe-area-inset-bottom, 0);
}
</style>
