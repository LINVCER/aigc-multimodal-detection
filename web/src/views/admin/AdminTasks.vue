<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAdminTasks, getTaskStats, batchDeleteTasks, batchRetryTasks, type AdminTask, type TaskStats } from '@/api/admin'
import { retryTask, cancelTask, deleteTask } from '@/api/detect'

/**
 * 任务列表：状态 KPI（可点筛选）· 筛选条（含日期 / 达标 / 模型版本）· 服务端排序 · 多选批量重试 / 删除 · 行内重试 / 取消 / 删除 · 详情抽屉 · 导出 CSV
 */
const router = useRouter()
const route = useRoute()

const SCENARIO_LABEL: Record<string, string> = { academic_bachelor: '学术·本科', academic_master: '学术·硕士', academic_phd: '学术·博士', job_report: '职业报告', self_media: '自媒体', other: '其他' }
const STATUS_TAG: Record<string, { text: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  PENDING: { text: '排队中', type: 'info' }, RUNNING: { text: '检测中', type: 'warning' }, DONE: { text: '已完成', type: 'success' }, FAILED: { text: '失败', type: 'danger' },
}

const stats = ref<TaskStats | null>(null)
const filter = reactive<{ status: string; scenario: string; keyword: string; userId?: number; minAiRate?: number; maxAiRate?: number; pass: '' | 'true' | 'false'; modelVersion: string; range: [string, string] | null; sortBy: string; sortOrder: 'asc' | 'desc' }>({
  status: '', scenario: '', keyword: '', pass: '', modelVersion: '', range: null, sortBy: '', sortOrder: 'desc',
})
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rows = ref<AdminTask[]>([])
const loading = ref(false)
const selected = ref<AdminTask[]>([])

async function loadStats() { try { stats.value = await getTaskStats() } catch { stats.value = null } }
async function load() {
  loading.value = true
  try {
    const resp = await listAdminTasks({
      status: filter.status || undefined, scenario: filter.scenario || undefined, keyword: filter.keyword || undefined, userId: filter.userId,
      minAiRate: filter.minAiRate, maxAiRate: filter.maxAiRate, pass: filter.pass === '' ? undefined : filter.pass === 'true',
      modelVersion: filter.modelVersion || undefined, dateFrom: filter.range?.[0], dateTo: filter.range?.[1],
      sortBy: filter.sortBy || undefined, sortOrder: filter.sortOrder, pageNum: pageNum.value, pageSize: pageSize.value,
    })
    rows.value = resp.rows
    total.value = resp.total
  } finally { loading.value = false }
}
function refreshAll() { loadStats(); load() }
function search() { pageNum.value = 1; load() }
function reset() { Object.assign(filter, { status: '', scenario: '', keyword: '', userId: undefined, minAiRate: undefined, maxAiRate: undefined, pass: '', modelVersion: '', range: null, sortBy: '', sortOrder: 'desc' }); search() }
function quickStatus(s: string) { filter.status = filter.status === s ? '' : s; search() }
function onSortChange({ prop, order }: { prop: string; order: 'ascending' | 'descending' | null }) { filter.sortBy = order ? prop : ''; filter.sortOrder = order === 'ascending' ? 'asc' : 'desc'; load() }

function aiRateColor(rate: number | null, threshold: number) { if (rate == null) return 'var(--label-tertiary)'; return rate <= threshold ? '#1B7F3E' : rate <= threshold * 1.5 ? '#B26200' : '#C62A22' }
const fmt = (s?: string | null) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')
const fmtSize = (n?: number | null) => (n == null ? '—' : n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : (n / 1024).toFixed(0) + ' KB')

/* ---------- 行内操作 ---------- */
async function onRetry(t: AdminTask) { await retryTask(t.id); ElMessage.success('已重新提交'); refreshAll() }
async function onCancel(t: AdminTask) {
  try { await ElMessageBox.confirm(`取消任务 #${t.id}「${t.paperTitle}」？`, '取消任务', { type: 'warning' }) } catch { return }
  await cancelTask(t.id); ElMessage.success('已取消'); refreshAll()
}
async function onDelete(t: AdminTask) {
  try { await ElMessageBox.confirm(`删除任务 #${t.id} 及其段落结果？不可恢复。`, '删除任务', { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' }) } catch { return }
  await deleteTask(t.id); ElMessage.success('已删除'); if (drawer.task?.id === t.id) drawer.open = false; refreshAll()
}

/* ---------- 批量 ---------- */
const failedSelected = computed(() => selected.value.filter((t) => t.status === 'FAILED'))
async function onBatchRetry() {
  const ids = failedSelected.value.map((t) => t.id)
  if (!ids.length) { ElMessage.info('所选任务里没有失败的'); return }
  const r = await batchRetryTasks(ids); ElMessage.success(`已重试 ${r.retried} 个`); selected.value = []; refreshAll()
}
async function onBatchDelete() {
  const ids = selected.value.map((t) => t.id)
  try { await ElMessageBox.confirm(`删除 ${ids.length} 个任务及其段落结果？不可恢复。`, '批量删除', { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' }) } catch { return }
  const r = await batchDeleteTasks(ids); ElMessage.success(`已删除 ${r.deleted} 个`); selected.value = []; refreshAll()
}

/* ---------- 导出 ---------- */
function exportCsv() {
  if (!rows.value.length) { ElMessage.info('当前没有数据'); return }
  const head = ['任务 ID', '用户', '论文标题', '场景', 'AI 率', '红线', '是否达标', '状态', '字数', '模型', '提交时间', '完成时间']
  const esc = (v: unknown) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const lines = rows.value.map((t) => [t.id, t.userLabel, t.paperTitle, SCENARIO_LABEL[t.scenario] || t.scenario, t.aiRate ?? '', t.threshold, t.aiRate == null ? '' : t.aiRate <= t.threshold ? '达标' : '超线', STATUS_TAG[t.status]?.text || t.status, t.wordCount ?? '', t.modelVersion, fmt(t.createdAt), fmt(t.finishedAt)].map(esc).join(','))
  const blob = new Blob(['﻿' + [head.map(esc).join(','), ...lines].join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `tasks-${new Date().toISOString().slice(0, 10)}.csv`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/* ---------- 详情抽屉 ---------- */
const drawer = reactive<{ open: boolean; task: AdminTask | null }>({ open: false, task: null })
function openDetail(t: AdminTask) { drawer.task = t; drawer.open = true }

onMounted(() => {
  const uid = Number(route.query.userId)
  if (uid) filter.userId = uid
  if (typeof route.query.status === 'string') filter.status = route.query.status
  refreshAll()
})
</script>

<template>
  <div class="page-head">
    <div><div class="page-title">任务列表</div><div class="page-sub">全平台检测任务；单条可重试 / 取消 / 删除，多选可批量</div></div>
    <div class="head-actions"><el-button :disabled="!rows.length" @click="exportCsv">导出 CSV</el-button><el-button @click="refreshAll">刷新</el-button></div>
  </div>

  <div class="kpi-row">
    <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">任务总数</div><div class="kpi-value">{{ stats?.total ?? '—' }}</div><div class="kpi-foot">今日 {{ stats?.today ?? '—' }}<template v-if="stats?.todayFailed"> · 失败 {{ stats.todayFailed }}</template></div></el-card>
    <el-card v-for="s in ['PENDING', 'RUNNING', 'DONE', 'FAILED']" :key="s" class="kpi" :class="{ on: filter.status === s }" body-style="padding: 14px 16px" @click="quickStatus(s)">
      <div class="kpi-label">{{ STATUS_TAG[s].text }}</div>
      <div class="kpi-value" :class="s === 'FAILED' && (stats?.byStatus[s] || 0) > 0 ? 'bad' : s === 'DONE' ? 'ok' : ''">{{ stats?.byStatus[s] ?? '—' }}</div>
      <div class="kpi-foot">点击筛选</div>
    </el-card>
    <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">超线占比</div><div class="kpi-value" :class="{ bad: (stats?.overRate || 0) > 50 }">{{ stats?.overRate == null ? '—' : stats.overRate + '%' }}</div><div class="kpi-foot">已完成中超线 {{ stats?.over ?? '—' }} 个</div></el-card>
  </div>

  <el-card class="filter-card" body-style="padding: 14px 18px">
    <div class="filter-row">
      <el-input v-model="filter.keyword" placeholder="论文标题" clearable style="width: 220px" @keyup.enter="search" @clear="search" />
      <el-select v-model="filter.scenario" placeholder="全部场景" clearable style="width: 140px" @change="search"><el-option v-for="(v, k) in SCENARIO_LABEL" :key="k" :label="v" :value="k" /></el-select>
      <el-select v-model="filter.pass" placeholder="达标 / 超线" clearable style="width: 120px" @change="search"><el-option label="达标" value="true" /><el-option label="超线" value="false" /></el-select>
      <el-date-picker v-model="filter.range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" unlink-panels style="width: 240px" @change="search" />
      <el-input-number v-model="filter.userId" placeholder="用户 ID" :controls="false" style="width: 110px" @change="search" />
      <el-input-number v-model="filter.minAiRate" placeholder="AI 率 ≥" :min="0" :max="100" :controls="false" style="width: 100px" />
      <el-input-number v-model="filter.maxAiRate" placeholder="AI 率 ≤" :min="0" :max="100" :controls="false" style="width: 100px" />
      <el-input v-model="filter.modelVersion" placeholder="模型版本" clearable style="width: 140px" @keyup.enter="search" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>
    <transition name="fade">
      <div v-if="selected.length" class="batch-bar">
        <span>已选 {{ selected.length }} 个<template v-if="failedSelected.length">，其中失败 {{ failedSelected.length }}</template></span>
        <el-button size="small" type="warning" plain :disabled="!failedSelected.length" @click="onBatchRetry">批量重试失败</el-button>
        <el-button size="small" type="danger" plain @click="onBatchDelete">批量删除</el-button>
        <el-button size="small" link @click="selected = []">取消选择</el-button>
      </div>
    </transition>
  </el-card>

  <el-card class="table-card" body-style="padding: 0">
    <el-table v-loading="loading" :data="rows" row-key="id" @selection-change="(v: AdminTask[]) => (selected = v)" @sort-change="onSortChange">
      <template #empty><div class="empty"><div class="empty-title">没有符合条件的任务</div><div class="empty-sub">换个筛选条件试试</div></div></template>
      <el-table-column type="selection" width="44" />
      <el-table-column label="任务" min-width="280">
        <template #default="{ row }">
          <div class="task-cell" @click="openDetail(row)">
            <div class="task-title">{{ row.paperTitle || '未命名' }}</div>
            <div class="task-sub">#{{ row.id }} · <a class="link" @click.stop="router.push({ path: '/admin/users', query: { userId: row.userId } })">{{ row.userLabel }}</a><template v-if="row.parentTaskId"> · 修改稿（上次 #{{ row.parentTaskId }}）</template></div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="场景" width="110"><template #default="{ row }">{{ SCENARIO_LABEL[row.scenario] || row.scenario }}</template></el-table-column>
      <el-table-column label="AI 率" width="120" align="right" prop="aiRate" sortable="custom">
        <template #default="{ row }">
          <template v-if="row.aiRate != null"><b :style="{ color: aiRateColor(row.aiRate, row.threshold) }">{{ row.aiRate.toFixed(1) }}%</b><div class="cell-sub">红线 {{ row.threshold }}% · {{ row.aiRate <= row.threshold ? '达标' : '超线' }}</div></template>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="字数" width="90" align="right" prop="wordCount" sortable="custom"><template #default="{ row }"><span class="muted">{{ row.wordCount ?? '—' }}</span></template></el-table-column>
      <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="STATUS_TAG[row.status]?.type" size="small" effect="light">{{ STATUS_TAG[row.status]?.text || row.status }}</el-tag></template></el-table-column>
      <el-table-column label="模型" width="150" show-overflow-tooltip><template #default="{ row }"><span class="muted small">{{ row.modelVersion }}</span></template></el-table-column>
      <el-table-column label="提交时间" width="150" prop="createdAt" sortable="custom"><template #default="{ row }"><span class="muted">{{ fmt(row.createdAt) }}</span></template></el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="router.push(`/task/${row.id}`)">报告</el-button>
          <el-button v-if="row.status === 'FAILED'" size="small" link type="warning" @click="onRetry(row)">重试</el-button>
          <el-button v-else-if="row.status === 'PENDING' || row.status === 'RUNNING'" size="small" link @click="onCancel(row)">取消</el-button>
          <el-button size="small" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager-row"><span class="muted small">共 {{ total }} 个任务</span><el-pagination v-model:current-page="pageNum" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
  </el-card>

  <el-drawer v-model="drawer.open" size="420px" :with-header="false">
    <div v-if="drawer.task" class="dr">
      <div class="dr-head">
        <div class="dr-title">{{ drawer.task.paperTitle || '未命名' }}</div>
        <el-tag :type="STATUS_TAG[drawer.task.status]?.type" effect="light">{{ STATUS_TAG[drawer.task.status]?.text }}</el-tag>
      </div>
      <div v-if="drawer.task.aiRate != null" class="dr-rate" :style="{ color: aiRateColor(drawer.task.aiRate, drawer.task.threshold) }">{{ drawer.task.aiRate.toFixed(1) }}%<span class="muted small"> · 红线 {{ drawer.task.threshold }}% · {{ drawer.task.aiRate <= drawer.task.threshold ? '达标' : '超线' }}</span></div>
      <dl class="kv">
        <dt>任务 ID</dt><dd>#{{ drawer.task.id }}<template v-if="drawer.task.parentTaskId"> · 修改稿，上次 #{{ drawer.task.parentTaskId }}</template></dd>
        <dt>用户</dt><dd><a class="link" @click="router.push({ path: '/admin/users', query: { userId: drawer.task.userId } })">{{ drawer.task.userLabel }}</a></dd>
        <dt>场景</dt><dd>{{ SCENARIO_LABEL[drawer.task.scenario] || drawer.task.scenario }}</dd>
        <dt>文件</dt><dd>{{ drawer.task.originalFilename || '—' }} <span class="muted small">{{ fmtSize(drawer.task.fileSize) }}</span></dd>
        <dt>字数</dt><dd>{{ drawer.task.wordCount ?? '—' }}<template v-if="drawer.task.bodyParagraphCount != null"> · 正文 {{ drawer.task.bodyParagraphCount }} 段<template v-if="drawer.task.excludedParagraphCount"> · 排除 {{ drawer.task.excludedParagraphCount }}</template></template></dd>
        <dt>模型</dt><dd>{{ drawer.task.modelVersion }}</dd>
        <dt>提交</dt><dd>{{ fmt(drawer.task.createdAt) }}</dd>
        <dt>完成</dt><dd>{{ fmt(drawer.task.finishedAt) }}</dd>
      </dl>
      <div class="dr-actions">
        <el-button type="primary" @click="router.push(`/task/${drawer.task.id}`)">打开报告</el-button>
        <el-button v-if="drawer.task.status === 'FAILED'" type="warning" plain @click="onRetry(drawer.task)">重试</el-button>
        <el-button v-else-if="drawer.task.status === 'PENDING' || drawer.task.status === 'RUNNING'" @click="onCancel(drawer.task)">取消</el-button>
        <el-button type="danger" plain @click="onDelete(drawer.task)">删除</el-button>
      </div>
      <div class="muted small">运营视图不含原文段落；需要看段落请打开报告。</div>
    </div>
  </el-drawer>
</template>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.page-title { font-size: 22px; font-weight: 700; letter-spacing: -0.4px; } .page-sub { font-size: 13px; color: var(--label-secondary); margin-top: 4px; }
.head-actions { display: flex; gap: 8px; }
.kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 14px; }
.kpi { cursor: pointer; border: 1px solid transparent; transition: border-color .15s, transform .15s; } .kpi:hover:not(.static) { transform: translateY(-1px); } .kpi.on { border-color: var(--system-blue); } .kpi.static { cursor: default; }
.kpi-label { font-size: 12px; color: var(--label-secondary); } .kpi-value { font-size: 26px; font-weight: 700; letter-spacing: -0.5px; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi-value.ok { color: #1B7F3E; } .kpi-value.bad { color: #C62A22; } .kpi-foot { font-size: 11px; color: var(--label-tertiary); margin-top: 6px; min-height: 14px; }
.filter-card { margin-bottom: 12px; } .filter-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.batch-bar { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 8px 12px; border-radius: 10px; background: rgba(0, 122, 255, 0.07); font-size: 13px; }
.fade-enter-active, .fade-leave-active { transition: opacity .15s; } .fade-enter-from, .fade-leave-to { opacity: 0; }
.table-card :deep(.el-table) { --el-table-header-bg-color: #FAFBFC; }
.task-cell { cursor: pointer; } .task-title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .task-cell:hover .task-title { color: var(--system-blue); }
.task-sub { font-size: 12px; color: var(--label-secondary); } .cell-sub { font-size: 11px; color: var(--label-tertiary); }
.link { color: var(--system-blue); cursor: pointer; } .muted { color: var(--label-secondary); } .small { font-size: 12px; }
.empty { padding: 36px 0; } .empty-title { font-weight: 600; color: var(--label); } .empty-sub { font-size: 12px; color: var(--label-tertiary); margin-top: 4px; }
.pager-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; }
.dr { display: flex; flex-direction: column; gap: 16px; } .dr-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; } .dr-title { font-size: 18px; font-weight: 700; line-height: 1.3; }
.dr-rate { font-size: 32px; font-weight: 700; letter-spacing: -0.8px; font-variant-numeric: tabular-nums; }
.kv { display: grid; grid-template-columns: 64px 1fr; gap: 8px 12px; margin: 0; font-size: 14px; padding-top: 12px; border-top: 1px solid var(--label-quaternary); } .kv dt { color: var(--label-secondary); } .kv dd { margin: 0; }
.dr-actions { display: flex; gap: 8px; flex-wrap: wrap; }
@media (max-width: 1200px) { .kpi-row { grid-template-columns: repeat(3, 1fr); } }
</style>
