<script setup>
import { onLaunch } from '@dcloudio/uni-app'
import { useAuth } from '@/store/auth'

onLaunch(() => {
  const auth = useAuth()
  auth.restore()
  // 未登录跳登录页；已登录直接留在 tabBar 页
  if (!auth.token) {
    uni.reLaunch({ url: '/pages/login/login' })
  }
})
</script>

<style lang="scss">
/* 全局 reset & 基础字号 */
page {
  background-color: #f3f4f6;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Helvetica Neue', Helvetica, 'Microsoft YaHei', Arial, sans-serif;
  color: #111827;
  font-size: 28rpx;
}

view, text {
  box-sizing: border-box;
}
</style>
