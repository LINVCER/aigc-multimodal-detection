<script setup>
import { onLaunch } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'

onLaunch(() => {
  const auth = useAuth()
  auth.restore()
  if (!auth.token) {
    uni.reLaunch({ url: '/pages/login/login' })
  }
})
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
.uni-tabbar__item:has(.uni-tabbar__icon:empty) .uni-tabbar__label,
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
