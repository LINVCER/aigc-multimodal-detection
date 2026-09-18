<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listTasks, deleteTask, retryTask } from '@/api/detect'
import { useAuthStore } from '@/stores/auth'
import type { DetectTask } from '@/api/types'

const router = useRouter()
const auth = useAuthStore()

const tasks = ref<DetectTask[]>([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const statusFilter = ref('')

let pollTimer: any = null

async function load() {
  loading.value = true
  try {
    const data = await listTasks({
      pageNum: 1, pageSize: 50,
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
    })
    tasks.value = data.rows
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const hasRunning = computed(() => tasks.value.some(t => t.status === 'PENDING' || t.status === 'RUNNING'))

function ensurePolling() {
  if (pollTimer || !hasRunning.value) return
  pollTimer = setInterval(async () => {
    await load()
    if (!hasRunning.value) stopPolling()
  }, 4000)
}
function stopPolling() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

onMounted(async () => { await load(); ensurePolling() })
onUnmounted(stopPolling)

function aiRateColor(rate: number | null, threshold: number): string {
  if (rate == null) return '#9ca3af'
  if (rate <= threshold) return '#10b981'
  if (rate <= threshold * 1.5) return '#f59e0b'
  return '#ef4444'
}

const STATUS_TAG = {
  PENDING: { type: 'info', text: '排队中' },
  RUNNING: { type: 'warning', text: '检测中' },
  DONE:    { type: 'success', text: '已完成' },
  FAILED:  { type: 'danger', text: '失败' },
} as const

const DEGREE_LABEL = { BACHELOR: '本科', MASTER: '硕士', PHD: '博士' } as const

function goDetail(id: number) { router.push({ name: 'TaskDetail', params: { id } }) }

async function onRetry(id: number) {
  await retryTask(id)
  ElMessage.success('已重新提交')
  await load()
  ensurePolling()
}

async function onDelete(id: number) {
  await ElMessageBox.confirm('确认删除该检测记录？', '提示', { type: 'warning' })
  await deleteTask(id)
  ElMessage.success('已删除')
  await load()
}

function logout() { auth.logout(); router.replace('/login') }
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <span class="brand">论文AIGC检测</span>
        <div class="user">
          <span>{{ auth.user?.realName || auth.user?.username || '' }}</span>
          <el-button link @click="logout">退出</el-button>
        </div>
      </div>
    </el-header>

    <el-main class="main">
      <div class="toolbar">
        <el-input v-model="keyword" placeholder="搜索论文标题" clearable @keyup.enter="load" style="width: 300px" />
        <el-select v-model="statusFilter" placeholder="全部状态" clearable @change="load" style="width: 160px">
          <el-option label="进行中" value="RUNNING" />
          <el-option label="已完成" value="DONE" />
          <el-option label="失败" value="FAILED" />
        </el-select>
        <el-button @click="load">刷新</el-button>
        <el-button type="primary" @click="router.push('/upload')">+ 提交检测</el-button>
      </div>

      <el-table :data="tasks" v-loading="loading" stripe style="width: 100%; margin-top: 16px">
        <el-table-column prop="paperTitle" label="论文标题" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">
            <a class="title-link" @click="goDetail(row.id)">{{ row.paperTitle }}</a>
          </template>
        </el-table-column>
        <el-table-column label="学位" width="90">
          <template #default="{ row }">{{ DEGREE_LABEL[row.degreeType as keyof typeof DEGREE_LABEL] || row.degreeType }}</template>
        </el-table-column>
        <el-table-column label="红线" width="80">
          <template #default="{ row }">{{ row.threshold }}%</template>
        </el-table-column>
        <el-table-column label="AI 率" width="110">
          <template #default="{ row }">
            <span v-if="row.aiRate == null" style="color: #9ca3af">—</span>
            <span v-else :style="{ color: aiRateColor(row.aiRate, row.threshold), fontWeight: 700 }">
              {{ row.aiRate.toFixed(1) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="(STATUS_TAG[row.status as keyof typeof STATUS_TAG] || STATUS_TAG.PENDING).type" size="small">
              {{ (STATUS_TAG[row.status as keyof typeof STATUS_TAG] || STATUS_TAG.PENDING).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="提交时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="goDetail(row.id)">查看</el-button>
            <el-button v-if="row.status === 'FAILED'" link @click="onRetry(row.id)">重试</el-button>
            <el-button link type="danger" @click="onDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header {
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
  padding: 0;
}
.header-inner {
  height: 60px;
  padding: 0 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.brand { font-size: 18px; font-weight: 700; color: #1a56db; }
.user { display: flex; align-items: center; gap: 12px; color: #4b5563; font-size: 14px; }
.main { padding: 24px; }
.toolbar { display: flex; gap: 12px; align-items: center; }
.title-link { color: #1a56db; cursor: pointer; }
.title-link:hover { text-decoration: underline; }
</style>
