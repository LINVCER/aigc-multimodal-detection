import { createRouter, createWebHashHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('@/views/Dashboard.vue') },
  { path: '/upload', name: 'Upload', component: () => import('@/views/Upload.vue') },
  { path: '/task/:id', name: 'TaskDetail', component: () => import('@/views/TaskDetail.vue'), props: true },
  { path: '/profile', name: 'Profile', component: () => import('@/views/Profile.vue') },

  // ============ 运营后台 · Wave 3.e ============
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresOpsAdmin: true },
    redirect: '/admin/dashboard',
    children: [
      { path: 'dashboard', name: 'AdminDashboard', component: () => import('@/views/admin/AdminDashboard.vue') },
      { path: 'users',     name: 'AdminUsers',     component: () => import('@/views/admin/AdminUsers.vue') },
      { path: 'tasks',     name: 'AdminTasks',     component: () => import('@/views/admin/AdminTasks.vue') },
      { path: 'feedback',  name: 'AdminFeedback',  component: () => import('@/views/admin/AdminFeedback.vue') },
    ],
  },

  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFound.vue'), meta: { public: true } },
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
  // W3.e 后台仅 OPS_ADMIN 可进；W3.c 登录未接入前，本地/mock 场景默认放行
  if (to.meta.requiresOpsAdmin) {
    const role = auth.user?.role || ''
    if (role && role !== 'OPS_ADMIN' && role !== 'ADMIN') {
      return { name: 'Dashboard' }
    }
  }
  return true
})

export default router
