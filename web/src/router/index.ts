import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  { path: '/login', name: 'Login', component: () => import('@/views/Login.vue'), meta: { public: true } },
  { path: '/privacy', name: 'Privacy', component: () => import('@/views/Privacy.vue'), meta: { public: true } },
  { path: '/verify/:reportNo?', name: 'Verify', component: () => import('@/views/Verify.vue'), props: true, meta: { public: true } },
  { path: '/s/:token', name: 'SharedReport', component: () => import('@/views/SharedReport.vue'), props: true, meta: { public: true } },
  { path: '/', name: 'Landing', component: () => import('@/views/Landing.vue'), meta: { public: true } },
  { path: '/schools', name: 'Schools', component: () => import('@/views/Schools.vue'), meta: { public: true } },
  { path: '/schools/:id', name: 'SchoolDetail', component: () => import('@/views/SchoolDetail.vue'), props: true, meta: { public: true } },
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
      { path: 'assistant', name: 'AdminAssistant', component: () => import('@/views/admin/AdminAssistant.vue') },
      { path: 'analytics', name: 'AdminAnalytics', component: () => import('@/views/admin/AdminAnalytics.vue') },
      { path: 'schools',   name: 'AdminSchools',   component: () => import('@/views/admin/AdminSchools.vue') },
    ],
  },

  { path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFound.vue'), meta: { public: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** 管理端独立实例（npm run dev:admin，端口 5174）：本实例只开放后台与登录页 */
const ADMIN_ONLY = import.meta.env.MODE === 'admin'

router.beforeEach((to) => {
  if (ADMIN_ONLY && !to.path.startsWith('/admin') && to.name !== 'Login') {
    return { path: '/admin/dashboard' }
  }
  if (to.meta.public) return true
  const auth = useAuthStore()
  if (!auth.token) auth.restore()
  if (!auth.token) return { name: 'Login', query: { redirect: to.fullPath } }
  // W3.e 后台仅 OPS_ADMIN 可进；W3.c 登录未接入前，本地/mock 场景默认放行
  if (to.meta.requiresOpsAdmin) {
    const role = auth.user?.role || ''
    if (role && role !== 'OPS_ADMIN' && role !== 'ADMIN') {
      // admin 独立实例下不能弹去 Dashboard（会被实例守卫弹回 → 无限循环），回登录页提示
      if (ADMIN_ONLY) {
        ElMessage.warning('这个账号进不了运营后台，请用管理员账号')
        return { name: 'Login', query: { redirect: to.fullPath } }
      }
      return { name: 'Dashboard' }
    }
  }
  return true
})

export default router
