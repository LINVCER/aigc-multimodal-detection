import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/upload', name: 'Upload', component: () => import('@/views/Upload.vue') },
  { path: '/task/:id', name: 'TaskDetail', component: () => import('@/views/TaskDetail.vue'), props: true },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.token) auth.restore()
  if (!auth.token) return { name: 'Login', query: { redirect: to.fullPath } }
  return true
})

export default router
