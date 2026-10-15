import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8080'   // 对齐若依基座 application.yml 默认 server.port
  // 管理端独立端口：npm run dev:admin → 5174，只跑 /admin（router 守卫圈定）
  const isAdmin = mode === 'admin'

  return {
    plugins: [vue()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      host: true,
      port: isAdmin ? 5174 : 5173,
      open: isAdmin ? '/admin/dashboard' : false,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
        // 后台 admin 接口无 /api 前缀（@RequestMapping("/admin/...")），dev 需单独代理；
        // 浏览器导航到 /admin/*（SPA 路由）不转发，交给 vite history fallback
        '/admin': {
          target: apiTarget,
          changeOrigin: true,
          bypass: (req) => {
            if (req.headers.accept?.includes('text/html')) return req.url
          },
        },
      },
    },
  }
})
