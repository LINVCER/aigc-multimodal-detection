<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { getDetectAnalytics, rebuildDetectStatistics, listAdminTasks, type DetectAnalytics, type AdminTask } from '@/api/admin'

/**
 * 检测分析（detect-analytics-plan §5）：筛选器 → KPI → 趋势 → 分布 → 明细
 * 趋势 / 分布读物化表 detect_statistics_daily，明细查 detect_task。
 */

const router = useRouter()

const SCENARIO_LABEL: Record<string, string> = {
  academic_bachelor: '学术·本科', academic_master: '学术·硕士', academic_phd: '学术·博士',
  job_report: '职业报告', self_media: '自媒体', other: '其他',
}
const SCENARIO_COLOR: Record<string, string> = {
  academic_bachelor: '#007AFF', academic_master: '#5AC8FA', academic_phd: '#AF52DE',
  job_report: '#FF9500', self_media: '#FF2D55', other: '#8E8E93',
}
const STATUS_LABEL: Record<string, string> = { PENDING: '排队中', RUNNING: '检测中', DONE: '已完成', FAILED: '失败' }
const SOURCE_LABEL: Record<string, string> = { human: '人写', gpt: 'GPT', claude: 'Claude', qwen: '通义千问', deepseek: 'DeepSeek', glm: '智谱', kimi: 'Kimi', ernie: '文心', other: '其它' }
const BUCKET_LABEL: Record<string, string> = { '0-10': '0–10%', '10-20': '10–20%', '20-30': '20–30%', '30-50': '30–50%', '50-100': '50–100%' }

function isoDate(d: Date) { return d.toISOString().slice(0, 10) }
const today = new Date()
const filter = reactive<{ range: [string, string]; scenario: string; status: string; rateBucket: string; pass: '' | 'true' | 'false'; modelVersion: string }>({
  range: [isoDate(new Date(today.getTime() - 29 * 86400000)), isoDate(today)],
  scenario: '', status: '', rateBucket: '', pass: '', modelVersion: '',
})

const data = ref<DetectAnalytics | null>(null)
const loading = ref(false)
const rebuilding = ref(false)

async function load() {
  loading.value = true
  try {
    data.value = await getDetectAnalytics({ dateFrom: filter.range[0], dateTo: filter.range[1], scenario: filter.scenario || undefined, status: filter.status || undefined })
    await loadRows()
  } finally { loading.value = false }
}

async function onRebuild() {
  await ElMessageBox.confirm('从 detect_task 全量重算统计表（首次上线补历史、或怀疑计数漂移时用）。继续？', '重算统计', { type: 'warning' })
  rebuilding.value = true
  try {
    const r = await rebuildDetectStatistics(0)
    ElMessage.success(`已重算 ${r.rows} 行`)
    await load()
  } finally { rebuilding.value = false }
}

/* ==================== 趋势折线 ==================== */
const trendW = 800, trendH = 180
const pad = { l: 40, r: 12, t: 12, b: 24 }
const inner = { w: trendW - pad.l - pad.r, h: trendH - pad.t - pad.b }
function line(field: 'total' | 'avgAiRate'): string {
  if (!data.value) return ''
  const rows = data.value.trend
  const max = Math.max(1, ...rows.map((r) => Number(r[field] || 0)))
  const step = inner.w / Math.max(1, rows.length - 1)
  return rows.map((r, i) => `${(pad.l + i * step).toFixed(1)},${(pad.t + inner.h * (1 - Number(r[field] || 0) / max)).toFixed(1)}`).join(' ')
}

/* ==================== 分布条 ==================== */
function bars(dist: Record<string, number> | undefined, label: Record<string, string>, color?: Record<string, string>) {
  if (!dist) return []
  const entries = Object.entries(dist)
  const max = Math.max(1, ...entries.map(([, v]) => v))
  const total = entries.reduce((s, [, v]) => s + v, 0)
  return entries.map(([k, v]) => ({ key: k, label: label[k] || k, value: v, width: (v / max) * 100, pct: total ? (v / total) * 100 : 0, color: color?.[k] || '#007AFF' }))
}
const scenarioBars = computed(() => bars(data.value?.scenarioDist, SCENARIO_LABEL, SCENARIO_COLOR))
const bucketBars = computed(() => bars(data.value?.rateBuckets, BUCKET_LABEL))
const sourceBars = computed(() => bars(data.value?.sourceDist, SOURCE_LABEL))
const statusBars = computed(() => bars(data.value?.statusDist, STATUS_LABEL))

/* ==================== 明细 ==================== */
const rows = ref<AdminTask[]>([])
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rowsLoading = ref(false)
async function loadRows() {
  rowsLoading.value = true
  try {
    const resp = await listAdminTasks({
      scenario: filter.scenario || undefined, status: filter.status || undefined,
      rateBucket: filter.rateBucket || undefined, pass: filter.pass === '' ? undefined : filter.pass === 'true',
      modelVersion: filter.modelVersion || undefined, dateFrom: filter.range[0], dateTo: filter.range[1],
      pageNum: pageNum.value, pageSize: pageSize.value,
    })
    rows.value = resp.rows
    total.value = resp.total
  } finally { rowsLoading.value = false }
}
function search() { pageNum.value = 1; load() }
function reset() {
  Object.assign(filter, { range: [isoDate(new Date(today.getTime() - 29 * 86400000)), isoDate(today)], scenario: '', status: '', rateBucket: '', pass: '', modelVersion: '' })
  search()
}
const pct = (v: number | null | undefined) => (v == null ? '—' : (v * 100).toFixed(1) + '%')
function rateColor(rate: number | null, threshold: number) {
  if (rate == null) return 'rgba(60,60,67,0.60)'
  return rate <= threshold ? '#34C759' : rate <= threshold * 1.5 ? '#FF9500' : '#FF3B30'
}

onMounted(load)
</script>

<template>
  <el-card class="filter-card">
    <div class="filter-row">
      <el-date-picker v-model="filter.range" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始" end-placeholder="结束" style="width: 260px" :clearable="false" />
      <el-select v-model="filter.scenario" placeholder="场景" clearable style="width: 140px">
        <el-option v-for="(v, k) in SCENARIO_LABEL" :key="k" :label="v" :value="k" />
      </el-select>
      <el-select v-model="filter.status" placeholder="状态" clearable style="width: 120px">
        <el-option v-for="(v, k) in STATUS_LABEL" :key="k" :label="v" :value="k" />
      </el-select>
      <el-select v-model="filter.rateBucket" placeholder="AI 率区间" clearable style="width: 130px">
        <el-option v-for="(v, k) in BUCKET_LABEL" :key="k" :label="v" :value="k" />
      </el-select>
      <el-select v-model="filter.pass" placeholder="达标" clearable style="width: 110px">
        <el-option label="达标" value="true" /><el-option label="超线" value="false" />
      </el-select>
      <el-input v-model="filter.modelVersion" placeholder="模型版本" clearable style="width: 140px" @keyup.enter="search" />
      <el-button type="primary" :loading="loading" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
      <el-button :loading="rebuilding" @click="onRebuild">重算统计</el-button>
      <span class="hint">AI 率区间 / 达标 / 模型版本只作用于明细表；趋势与分布按场景、状态、日期。</span>
    </div>
  </el-card>

  <div v-if="data" class="kpi-row">
    <el-card class="kpi-card"><div class="kpi-label">检测量</div><div class="kpi-value">{{ data.kpi.total }}</div></el-card>
    <el-card class="kpi-card"><div class="kpi-label">完成数</div><div class="kpi-value">{{ data.kpi.done }}</div></el-card>
    <el-card class="kpi-card"><div class="kpi-label">平均 AI 率</div><div class="kpi-value">{{ data.kpi.avgAiRate == null ? '—' : Number(data.kpi.avgAiRate).toFixed(1) + '%' }}</div></el-card>
    <el-card class="kpi-card"><div class="kpi-label">达标率</div><div class="kpi-value ok">{{ pct(data.kpi.passRate) }}</div></el-card>
    <el-card class="kpi-card"><div class="kpi-label">超线率</div><div class="kpi-value bad">{{ pct(data.kpi.overRate) }}</div></el-card>
  </div>

  <div v-if="data" class="mid-row">
    <el-card class="trend-card">
      <template #header>
        <div class="card-title"><span>趋势</span>
          <div class="legend"><span class="dot" style="background:#007AFF"></span><span>检测量</span><span class="dot" style="background:#FF9500"></span><span>平均 AI 率</span></div>
        </div>
      </template>
      <svg :viewBox="`0 0 ${trendW} ${trendH}`" width="100%" :style="{ height: trendH + 'px' }">
        <line :x1="pad.l" :y1="pad.t" :x2="pad.l" :y2="trendH - pad.b" stroke="#E5E5EA" />
        <line :x1="pad.l" :y1="trendH - pad.b" :x2="trendW - pad.r" :y2="trendH - pad.b" stroke="#E5E5EA" />
        <polyline :points="line('total')" fill="none" stroke="#007AFF" stroke-width="2" />
        <polyline :points="line('avgAiRate')" fill="none" stroke="#FF9500" stroke-width="2" />
      </svg>
      <div class="axis"><span>{{ data.from }}</span><span>{{ data.to }}</span></div>
    </el-card>
    <el-card>
      <template #header><div class="card-title">AI 率分桶（已完成）</div></template>
      <div v-for="b in bucketBars" :key="b.key" class="bar-row">
        <span class="bar-label">{{ b.label }}</span>
        <div class="bar"><div class="bar-fill" :style="{ width: b.width + '%', background: b.color }" /></div>
        <span class="bar-val">{{ b.value }} <span class="muted">{{ b.pct.toFixed(0) }}%</span></span>
      </div>
    </el-card>
  </div>

  <div v-if="data" class="tri-row">
    <el-card>
      <template #header><div class="card-title">场景分布</div></template>
      <div v-for="b in scenarioBars" :key="b.key" class="bar-row">
        <span class="bar-label">{{ b.label }}</span>
        <div class="bar"><div class="bar-fill" :style="{ width: b.width + '%', background: b.color }" /></div>
        <span class="bar-val">{{ b.value }}</span>
      </div>
    </el-card>
    <el-card>
      <template #header><div class="card-title">状态分布</div></template>
      <div v-for="b in statusBars" :key="b.key" class="bar-row">
        <span class="bar-label">{{ b.label }}</span>
        <div class="bar"><div class="bar-fill" :style="{ width: b.width + '%' }" /></div>
        <span class="bar-val">{{ b.value }}</span>
      </div>
      <div v-if="!statusBars.length" class="muted">无数据</div>
    </el-card>
    <el-card>
      <template #header><div class="card-title">溯源主标签（已完成）</div></template>
      <div v-for="b in sourceBars" :key="b.key" class="bar-row">
        <span class="bar-label">{{ b.label }}</span>
        <div class="bar"><div class="bar-fill" :style="{ width: b.width + '%', background: '#AF52DE' }" /></div>
        <span class="bar-val">{{ b.value }}</span>
      </div>
      <div v-if="!sourceBars.length" class="muted">无数据</div>
    </el-card>
  </div>

  <el-card class="table-card">
    <template #header><div class="card-title">明细</div></template>
    <el-table v-loading="rowsLoading" :data="rows" size="default" empty-text="暂无任务">
      <el-table-column prop="id" label="任务 ID" width="90" />
      <el-table-column prop="userLabel" label="用户" width="150" />
      <el-table-column prop="paperTitle" label="标题" min-width="240" show-overflow-tooltip />
      <el-table-column label="场景" width="110"><template #default="{ row }">{{ SCENARIO_LABEL[row.scenario] || row.scenario }}</template></el-table-column>
      <el-table-column label="AI 率" width="100">
        <template #default="{ row }"><span :style="{ color: rateColor(row.aiRate, row.threshold), fontWeight: 600 }">{{ row.aiRate == null ? '—' : row.aiRate.toFixed(1) + '%' }}</span></template>
      </el-table-column>
      <el-table-column label="达标" width="80"><template #default="{ row }"><el-tag v-if="row.aiRate != null" size="small" :type="row.aiRate <= row.threshold ? 'success' : 'danger'">{{ row.aiRate <= row.threshold ? '达标' : '超线' }}</el-tag><span v-else class="muted">—</span></template></el-table-column>
      <el-table-column label="状态" width="90"><template #default="{ row }">{{ STATUS_LABEL[row.status] || row.status }}</template></el-table-column>
      <el-table-column prop="modelVersion" label="模型" width="110" />
      <el-table-column prop="createdAt" label="时间" width="170" />
      <el-table-column label="操作" width="80" fixed="right"><template #default="{ row }"><el-button size="small" link type="primary" @click="router.push(`/task/${row.id}`)">查看</el-button></template></el-table-column>
    </el-table>
    <el-pagination class="pager" v-model:current-page="pageNum" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="loadRows" @current-change="loadRows" />
  </el-card>
</template>

<style scoped>
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.hint { font-size: 12px; color: rgba(60,60,67,0.60); }
.muted { color: rgba(60,60,67,0.60); font-size: 12px; }
.kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 16px; }
.kpi-card { text-align: center; }
.kpi-label { font-size: 13px; color: rgba(60,60,67,0.60); }
.kpi-value { font-size: 30px; font-weight: 600; letter-spacing: -0.5px; margin-top: 6px; color: #1C1C1E; }
.kpi-value.ok { color: #1B7F3E; } .kpi-value.bad { color: #C62A22; }
.mid-row { display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }
.tri-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 16px; }
.card-title { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.legend { display: flex; align-items: center; gap: 8px; font-size: 12px; color: rgba(60,60,67,0.72); font-weight: 400; }
.legend .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-left: 12px; }
.axis { display: flex; justify-content: space-between; font-size: 11px; color: rgba(60,60,67,0.45); padding: 0 12px 0 40px; }
.bar-row { display: flex; align-items: center; gap: 10px; padding: 5px 0; font-size: 13px; }
.bar-label { width: 80px; flex: none; color: rgba(60,60,67,0.72); }
.bar { flex: 1; height: 10px; border-radius: 99px; background: #F2F2F7; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 99px; background: #007AFF; }
.bar-val { width: 70px; text-align: right; font-variant-numeric: tabular-nums; }
.table-card :deep(.el-card__body) { padding: 0; }
.pager { justify-content: flex-end; padding: 16px; }
</style>
