<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { listAdminTasks, type AdminTask } from '@/api/admin'

const router = useRouter()

const filter = reactive<{
  status: string
  scenario: string
  keyword: string
  userId?: number
  minAiRate?: number
  maxAiRate?: number
}>({ status: '', scenario: '', keyword: '' })

const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rows = ref<AdminTask[]>([])
const loading = ref(false)

const SCENARIO_LABEL: Record<string, string> = {
  academic_bachelor: '学术·本科',
  academic_master:   '学术·硕士',
  academic_phd:      '学术·博士',
  job_report:        '职业报告',
  self_media:        '自媒体',
  other:             '其他',
}
const STATUS_TAG: Record<string, { text: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  PENDING: { text: '排队中', type: 'info'    },
  RUNNING: { text: '检测中', type: 'warning' },
  DONE:    { text: '已完成', type: 'success' },
  FAILED:  { text: '失败',   type: 'danger'  },
}

async function load() {
  loading.value = true
  try {
    const resp = await listAdminTasks({ ...filter, pageNum: pageNum.value, pageSize: pageSize.value })
    rows.value = resp.rows
    total.value = resp.total
  } finally { loading.value = false }
}
function search() { pageNum.value = 1; load() }
function reset() {
  Object.assign(filter, { status: '', scenario: '', keyword: '', userId: undefined, minAiRate: undefined, maxAiRate: undefined })
  search()
}

function aiRateColor(rate: number | null, threshold: number): string {
  if (rate == null) return 'rgba(60,60,67,0.60)'
  if (rate <= threshold) return '#34C759'
  if (rate <= threshold * 1.5) return '#FF9500'
  return '#FF3B30'
}

function viewDetail(id: number) {
  router.push(`/task/${id}`)
}

onMounted(load)
</script>

<template>
  <el-card class="filter-card">
    <div class="filter-row">
      <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px">
        <el-option label="排队中" value="PENDING" />
        <el-option label="检测中" value="RUNNING" />
        <el-option label="已完成" value="DONE" />
        <el-option label="失败"   value="FAILED" />
      </el-select>
      <el-select v-model="filter.scenario" placeholder="场景" clearable style="width: 150px">
        <el-option v-for="(v, k) in SCENARIO_LABEL" :key="k" :label="v" :value="k" />
      </el-select>
      <el-input v-model="filter.keyword" placeholder="论文标题" clearable style="width: 240px" @keyup.enter="search" />
      <el-input-number v-model="filter.userId" placeholder="用户 ID" :controls="false" style="width: 130px" />
      <el-input-number v-model="filter.minAiRate" placeholder="AI 率 ≥" :min="0" :max="100" :controls="false" style="width: 130px" />
      <el-input-number v-model="filter.maxAiRate" placeholder="AI 率 ≤" :min="0" :max="100" :controls="false" style="width: 130px" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>
  </el-card>

  <el-card class="table-card">
    <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无任务">
      <el-table-column prop="id" label="任务 ID" width="90" />
      <el-table-column prop="userLabel" label="用户" width="150" />
      <el-table-column prop="paperTitle" label="论文标题" min-width="240" show-overflow-tooltip />
      <el-table-column label="场景" width="120">
        <template #default="{ row }">{{ SCENARIO_LABEL[row.scenario] || row.scenario }}</template>
      </el-table-column>
      <el-table-column label="AI 率" width="100" align="right">
        <template #default="{ row }">
          <span v-if="row.aiRate != null" :style="{ color: aiRateColor(row.aiRate, row.threshold), fontWeight: 600 }">
            {{ row.aiRate.toFixed(1) }}%
          </span>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="红线" width="80" align="right">
        <template #default="{ row }">≤ {{ row.threshold }}%</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="STATUS_TAG[row.status]?.type" size="small">{{ STATUS_TAG[row.status]?.text || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="提交时间" width="170" />
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" link type="primary" @click="viewDetail(row.id)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      v-model:current-page="pageNum"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @size-change="load"
      @current-change="load"
    />
  </el-card>
</template>

<style scoped>
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.table-card :deep(.el-card__body) { padding: 0; }
.pager { justify-content: flex-end; padding: 16px; }
.muted { color: rgba(60,60,67,0.60); }
</style>
