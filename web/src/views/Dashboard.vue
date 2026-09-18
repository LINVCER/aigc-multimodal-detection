<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listTasks, deleteTask, retryTask } from '@/api/detect'
import { useAuthStore } from '@/stores/auth'
import EmptyState from '@/components/EmptyState.vue'
import Skeleton from '@/components/Skeleton.vue'
import type { DetectTask } from '@/api/types'

const router = useRouter()
const auth = useAuthStore()

const tasks = ref<DetectTask[]>([])
const total = ref(0)
const loading = ref(false)
const firstLoad = ref(true)
const error = ref('')
const keyword = ref('')
const statusFilter = ref('')

let pollTimer: any = null

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await listTasks({
      pageNum: 1, pageSize: 50,
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
    })
    tasks.value = data.rows
    total.value = data.total
  } catch (e: any) {
    error.value = e?.message || '加载失败'
  } finally {
    loading.value = false
    firstLoad.value = false
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
  if (rate == null) return 'var(--label-tertiary)'
  if (rate <= threshold) return 'var(--system-green)'
  if (rate <= threshold * 1.5) return 'var(--system-orange)'
  return 'var(--system-red)'
}

const STATUS_TAG = {
  PENDING: { type: 'info',    text: '排队中' },
  RUNNING: { type: 'warning', text: '检测中' },
  DONE:    { type: 'success', text: '已完成' },
  FAILED:  { type: 'danger',  text: '失败' },
} as const

const DEGREE_LABEL = { BACHELOR: '本科', MASTER: '硕士', PHD: '博士' } as const

const avatarLetter = computed(() =>
  (auth.user?.realName || auth.user?.username || 'U').charAt(0).toUpperCase())

function goDetail(id: number) { router.push({ name: 'TaskDetail', params: { id } }) }

async function onRetry(id: number) {
  await retryTask(id)
  ElMessage.success('已重新提交')
  await load(); ensurePolling()
}

async function onDelete(id: number) {
  await ElMessageBox.confirm('确认删除该检测记录？', '提示', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    confirmButtonClass: 'el-button--danger',
  })
  await deleteTask(id)
  ElMessage.success('已删除')
  await load()
}

const showEmpty = computed(() =>
  !loading.value && !error.value && tasks.value.length === 0)
const showEmptyFiltered = computed(() =>
  showEmpty.value && (keyword.value || statusFilter.value))
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <div class="brand-block">
          <span class="brand">论文AIGC检测</span>
        </div>
        <div class="header-actions">
          <div class="avatar-btn" @click="router.push('/profile')" :title="auth.user?.username || '我的'">
            {{ avatarLetter }}
          </div>
        </div>
      </div>
    </el-header>

    <el-main class="main">
      <div class="wrap">
        <!-- Large Title -->
        <div class="large-title-bar">
          <h1 class="large-title">检测记录</h1>
          <el-button type="primary" round size="large" @click="router.push('/upload')">+ 提交检测</el-button>
        </div>

        <!-- Toolbar -->
        <div class="toolbar">
          <el-input v-model="keyword" placeholder="搜索论文标题" clearable @change="load" style="width: 300px" />
          <el-select v-model="statusFilter" placeholder="全部状态" clearable @change="load" style="width: 160px">
            <el-option label="进行中" value="RUNNING" />
            <el-option label="已完成" value="DONE" />
            <el-option label="失败" value="FAILED" />
          </el-select>
        </div>

        <!-- 首次加载：骨架 -->
        <Skeleton v-if="loading && firstLoad" :rows="4" />

        <!-- 错误 -->
        <EmptyState
          v-else-if="error && tasks.length === 0"
          icon="⚠️" :title="error" desc="下拉刷新或检查网络后重试"
          action-text="重新加载" @action="load"
        />

        <!-- 空（无搜索）-->
        <EmptyState
          v-else-if="showEmpty && !showEmptyFiltered"
          icon="📭" title="还没有检测记录"
          desc="上传你的论文，几十秒内拿到 AI 率报告"
          action-text="去上传" @action="router.push('/upload')"
        />

        <!-- 空（有搜索无匹配）-->
        <EmptyState
          v-else-if="showEmptyFiltered"
          icon="🔎" title="没有匹配的记录" desc="换个关键词或清空筛选"
        />

        <!-- 表格 -->
        <el-card v-else class="table-card" body-style="padding:0">
          <el-table :data="tasks" v-loading="loading && !firstLoad" style="width: 100%">
            <el-table-column prop="paperTitle" label="论文标题" min-width="360" show-overflow-tooltip>
              <template #default="{ row }">
                <a class="title-link" @click="goDetail(row.id)">{{ row.paperTitle }}</a>
              </template>
            </el-table-column>
            <el-table-column label="学位" width="80">
              <template #default="{ row }">
                <span class="degree-tag">{{ DEGREE_LABEL[row.degreeType as keyof typeof DEGREE_LABEL] || row.degreeType }}</span>
              </template>
            </el-table-column>
            <el-table-column label="红线" width="70" align="center">
              <template #default="{ row }">{{ row.threshold }}%</template>
            </el-table-column>
            <el-table-column label="AI 率" width="110" align="right">
              <template #default="{ row }">
                <span v-if="row.aiRate == null" style="color: var(--label-tertiary)">—</span>
                <span v-else class="rate" :style="{ color: aiRateColor(row.aiRate, row.threshold) }">
                  {{ row.aiRate.toFixed(1) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
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
        </el-card>
      </div>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; background: var(--system-grouped-background); }

.header {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--label-quaternary);
  padding: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-inner {
  height: 56px; padding: 0 24px; display: flex;
  justify-content: space-between; align-items: center;
}
.brand-block { display: flex; align-items: center; gap: 12px; }
.brand { font-size: var(--fs-headline); font-weight: var(--fw-semibold); color: var(--label); letter-spacing: -0.2px; }

.header-actions { display: flex; align-items: center; gap: 12px; }
.avatar-btn {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, var(--system-blue) 0%, var(--system-teal) 100%);
  color: #fff; font-size: 14px; font-weight: var(--fw-semibold);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: transform var(--dur-fast) var(--ease-standard);
}
.avatar-btn:hover  { transform: scale(1.06); }
.avatar-btn:active { transform: scale(0.94); }

.main { padding: 32px 24px 48px; }
.wrap { max-width: 1200px; margin: 0 auto; }

.large-title-bar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24px;
}
.large-title {
  font-size: var(--fs-large-title);
  font-weight: var(--fw-bold);
  letter-spacing: -0.8px;
  margin: 0;
}

.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }

.title-link { color: var(--system-blue); cursor: pointer; }
.title-link:hover { text-decoration: underline; }

.degree-tag {
  background: rgba(0, 122, 255, 0.10);
  color: var(--system-blue);
  padding: 2px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: var(--fw-semibold);
}

.rate { font-weight: var(--fw-bold); font-variant-numeric: tabular-nums; letter-spacing: -0.3px; }
</style>
