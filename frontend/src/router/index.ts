import { createRouter, createWebHistory } from "vue-router"
import type { RouteRecordRaw } from "vue-router"

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue"),
    meta: { title: "登录" },
  },
  {
    path: "/",
    component: () => import("@/views/layout/MainLayout.vue"),
    redirect: "/dashboard",
    children: [
      {
        path: "dashboard",
        name: "Dashboard",
        component: () => import("@/views/Dashboard.vue"),
        meta: { title: "仪表盘" },
      },
      {
        path: "detect/text",
        name: "TextDetection",
        component: () => import("@/views/TextDetection.vue"),
        meta: { title: "文本检测" },
      },
      {
        path: "detect/image",
        name: "ImageDetection",
        component: () => import("@/views/ImageDetection.vue"),
        meta: { title: "图像检测" },
      },
      {
        path: "detect/audio",
        name: "AudioDetection",
        component: () => import("@/views/AudioDetection.vue"),
        meta: { title: "音频检测" },
      },
      {
        path: "detect/tampering",
        name: "TamperingDetection",
        component: () => import("@/views/TamperingDetection.vue"),
        meta: { title: "篡改检测" },
      },
      {
        path: "detect/thesis",
        name: "ThesisDetection",
        component: () => import("@/views/ThesisDetection.vue"),
        meta: { title: "论文检测" },
      },
      {
        path: "assistant",
        name: "AIAssistant",
        component: () => import("@/views/AIAssistant.vue"),
        meta: { title: "AI助手" },
      },
      {
        path: "detect/reduce",
        name: "ReduceAIGC",
        component: () => import("@/views/ReduceAIGC.vue"),
        meta: { title: "论文降AI" },
      },
      {
        path: "detect/batch",
        name: "BatchDetection",
        component: () => import("@/views/BatchDetection.vue"),
        meta: { title: "批量检测" },
      },
      {
        path: "history",
        name: "History",
        component: () => import("@/views/History.vue"),
        meta: { title: "检测历史" },
      },
      {
        path: "standards",
        name: "StandardsCompliance",
        component: () => import("@/views/StandardsCompliance.vue"),
        meta: { title: "标准合规" },
      },
      {
        path: "report/:taskId",
        name: "ReportView",
        component: () => import("@/views/ReportView.vue"),
        meta: { title: "检测报告" },
      },
      {
        path: "admin",
        name: "AdminPanel",
        component: () => import("@/views/AdminPanel.vue"),
        meta: { title: "管理后台", requiresAdmin: true },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem("access_token")
  if (to.name !== "Login" && !token) {
    next({ name: "Login" })
  } else if (to.meta?.requiresAdmin) {
    const userStr = localStorage.getItem("user_role")
    if (userStr === "admin") {
      next()
    } else {
      next({ name: "Dashboard" })
    }
  } else {
    next()
  }
})

export default router
