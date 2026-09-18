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
/* 全局基础：Apple 语义色板 + SF Pro 字栈 */
page {
  background-color: #F2F2F7;  /* systemGroupedBackground */
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'PingFang SC',
               'Helvetica Neue', Helvetica, 'Microsoft YaHei', sans-serif;
  color: #000000;
  font-size: 34rpx;           /* Body 17pt */
  line-height: 1.4;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

view, text, button, input { box-sizing: border-box; }

/* 覆盖 uni-app / 微信小程序默认按钮丑陋边框 */
button { border: none; }
button::after { border: none; }
</style>
