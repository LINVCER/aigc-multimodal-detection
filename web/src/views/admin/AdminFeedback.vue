<script setup lang="ts">
import { onMounted, reactive, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter, useRoute } from 'vue-router'
import {
  listFeedbackAdmin, handleFeedback, getFeedbackStats, batchHandleFeedback, listFeedbackSamples, setHardSampleVerdict, listHardSamples, hardSampleExportUrl,
  type FeedbackItem, type FeedbackStatus, type FeedbackCategory, type FeedbackStats, type HardSample, type HardSampleVerdict,
} from '@/api/feedback'
import { useAuthStore } from '@/stores/auth'

/**
 * 用户反馈：KPI（可点筛选）· 分类 / 状态 / 日期筛选 · 多选批量处置 · 处理抽屉（原文 · 申诉段级复核 · 快捷回复模板）· 误判样本池 tab（筛选 / 复核 / 导出 JSONL）
 */
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const tab = ref<'list' | 'samples'>('list')

const CATEGORY_LABEL: Record<string, string> = { appeal: '结果申诉', bug: 'Bug', suggestion: '建议' }
const CATEGORY_TAG: Record<string, 'danger' | 'warning' | ''> = { appeal: 'danger', bug: 'warning', suggestion: '' }
const STATUS_TAG: Record<FeedbackStatus, { text: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  PENDING: { text: '待处理', type: 'warning' }, PROCESSING: { text: '处理中', type: 'info' }, REPLIED: { text: '已回复', type: 'success' }, IGNORED: { text: '已忽略', type: 'info' },
}
const fmt = (s?: string | null) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')

/* ---------- KPI + 列表 ---------- */
const stats = ref<FeedbackStats | null>(null)
const filter = reactive<{ status: FeedbackStatus | ''; category: FeedbackCategory | ''; keyword: string; range: [string, string] | null }>({ status: '', category: '', keyword: '', range: null })
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rows = ref<FeedbackItem[]>([])
const loading = ref(false)
const selected = ref<FeedbackItem[]>([])

async function loadStats() { try { stats.value = await getFeedbackStats() } catch { stats.value = null } }
async function load() {
  loading.value = true
  try {
    const resp = await listFeedbackAdmin({ status: filter.status || undefined, category: filter.category || undefined, keyword: filter.keyword || undefined, dateFrom: filter.range?.[0], dateTo: filter.range?.[1], pageNum: pageNum.value, pageSize: pageSize.value })
    rows.value = resp.rows
    total.value = resp.total
  } finally { loading.value = false }
}
function refreshAll() { loadStats(); load() }
function search() { pageNum.value = 1; load() }
function reset() { Object.assign(filter, { status: '', category: '', keyword: '', range: null }); search() }
function quickStatus(s: FeedbackStatus | '') { filter.status = filter.status === s ? '' : s; search() }
function quickAppeal() { filter.category = 'appeal'; filter.status = 'PENDING'; search() }

/* ---------- 批量 ---------- */
async function onBatch(status: FeedbackStatus) {
  const ids = selected.value.map((f) => f.id)
  let reply: string | undefined
  if (status === 'REPLIED') {
    try {
      const r = await ElMessageBox.prompt('统一回复内容', `批量回复 ${ids.length} 条`, { inputType: 'textarea', inputPlaceholder: '将对所选每一条写入相同回复', confirmButtonText: '回复' })
      reply = String(r.value || '').trim()
      if (!reply) { ElMessage.warning('回复内容不能为空'); return }
    } catch { return }
  } else {
    try { await ElMessageBox.confirm(`将 ${ids.length} 条标记为「${STATUS_TAG[status].text}」？`, '批量处置', { type: 'warning' }) } catch { return }
  }
  const r = await batchHandleFeedback(ids, status, reply)
  ElMessage.success(`已更新 ${r.updated} 条`)
  selected.value = []
  refreshAll()
}

/* ---------- 处理抽屉 ---------- */
const QUICK_REPLIES = [
  { t: '申诉受理', c: '你好，已收到你对该段落判定的申诉。我们会在 3 个工作日内人工复核，复核结果会在这里回复，也可在「我的反馈」查看。' },
  { t: '确认误判', c: '经人工复核，你申诉的段落属于规范学术写作导致的统计特征偏差，不构成 AI 生成判定。相关段落已进入误判样本池用于改进模型。建议保留本回复作为说明材料。' },
  { t: '维持判定', c: '经人工复核，该段落在句长分布、套话连接词与用词重复度上与机器生成文本高度一致，维持原判定。你可以参考报告里的「为什么像 AI」自行重写后再测一次。' },
  { t: '建议已记录', c: '感谢反馈，这个建议已记录到产品需求池。如有进展会在版本说明中体现。' },
  { t: 'Bug 已修复', c: '感谢反馈，这个问题已定位并修复，将在下个版本上线。' },
]
const drawer = reactive<{ open: boolean; item: FeedbackItem | null; status: FeedbackStatus; reply: string; submitting: boolean; samples: HardSample[]; samplesLoading: boolean }>({ open: false, item: null, status: 'REPLIED', reply: '', submitting: false, samples: [], samplesLoading: false })
const VERDICT_LABEL: Record<HardSampleVerdict, string> = { confirm_fp: '确认误判', confirm_tp: '确认是 AI', unsure: '拿不准' }
const drawerDone = computed(() => drawer.item?.status === 'REPLIED' || drawer.item?.status === 'IGNORED')

async function openItem(row: FeedbackItem) {
  drawer.item = row
  drawer.status = row.status === 'PENDING' ? 'REPLIED' : row.status
  drawer.reply = row.handledReply || ''
  drawer.samples = []
  drawer.open = true
  if (row.category === 'appeal' && row.paragraphIdxs?.length) {
    drawer.samplesLoading = true
    try { drawer.samples = await listFeedbackSamples(row.id) } catch { drawer.samples = [] } finally { drawer.samplesLoading = false }
  }
}
async function verdict(s: HardSample, v: HardSampleVerdict) { await setHardSampleVerdict(s.id, v); s.opsVerdict = v; ElMessage.success(`第 ${s.paragraphIdx + 1} 段：${VERDICT_LABEL[v]}`) }
function useQuick(c: string) { drawer.reply = c; drawer.status = 'REPLIED' }
async function submit() {
  if (!drawer.item) return
  if (drawer.status === 'REPLIED' && !drawer.reply.trim()) { ElMessage.warning('回复内容不能为空'); return }
  drawer.submitting = true
  try {
    await handleFeedback(drawer.item.id, { status: drawer.status, reply: drawer.reply.trim() || undefined, handledBy: auth.user?.id })
    ElMessage.success('已保存')
    drawer.open = false
    refreshAll()
  } finally { drawer.submitting = false }
}

/* ---------- 样本池 ---------- */
const sf = reactive<{ verdict: string; days: number }>({ verdict: '', days: 90 })
const samples = ref<HardSample[]>([])
const samplesLoading = ref(false)
async function loadSamples() {
  samplesLoading.value = true
  try { samples.value = await listHardSamples({ verdict: sf.verdict || undefined, days: sf.days, limit: 300 }) } catch { samples.value = [] } finally { samplesLoading.value = false }
}
const sampleStats = computed(() => {
  const c = { pending: 0, confirm_fp: 0, confirm_tp: 0, unsure: 0 }
  for (const s of samples.value) { if (!s.opsVerdict) c.pending++; else c[s.opsVerdict]++ }
  return c
})
function openTab(t: 'list' | 'samples') { tab.value = t; if (t === 'samples' && !samples.value.length) loadSamples() }

onMounted(() => {
  if (typeof route.query.status === 'string') filter.status = route.query.status as FeedbackStatus
  if (route.query.tab === 'samples') openTab('samples')
  refreshAll()
})
</script>

<template>
  <div class="page-head">
    <div><div class="page-title">用户反馈</div><div class="page-sub">申诉 / Bug / 建议的处理，以及申诉段落的误判样本池</div></div>
    <el-radio-group :model-value="tab" @change="(v: any) => openTab(v)"><el-radio-button value="list">反馈处理</el-radio-button><el-radio-button value="samples">误判样本池</el-radio-button></el-radio-group>
  </div>

  <!-- ================= 反馈处理 ================= -->
  <template v-if="tab === 'list'">
    <div class="kpi-row">
      <el-card class="kpi" :class="{ on: filter.status === 'PENDING' && filter.category === 'appeal' }" body-style="padding: 14px 16px" @click="quickAppeal"><div class="kpi-label">待处理申诉</div><div class="kpi-value" :class="{ bad: (stats?.pendingAppeal || 0) > 0 }">{{ stats?.pendingAppeal ?? '—' }}</div><div class="kpi-foot">最优先</div></el-card>
      <el-card v-for="s in (['PENDING', 'PROCESSING', 'REPLIED', 'IGNORED'] as FeedbackStatus[])" :key="s" class="kpi" :class="{ on: filter.status === s && !filter.category }" body-style="padding: 14px 16px" @click="filter.category = ''; quickStatus(s)">
        <div class="kpi-label">{{ STATUS_TAG[s].text }}</div><div class="kpi-value" :class="s === 'PENDING' && (stats?.byStatus[s] || 0) > 0 ? 'warn' : ''">{{ stats?.byStatus[s] ?? '—' }}</div><div class="kpi-foot">点击筛选</div>
      </el-card>
      <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">今日新增</div><div class="kpi-value">{{ stats?.todayNew ?? '—' }}</div><div class="kpi-foot" v-if="stats">申诉 {{ stats.byCategory.appeal || 0 }} · Bug {{ stats.byCategory.bug || 0 }} · 建议 {{ stats.byCategory.suggestion || 0 }}</div></el-card>
    </div>

    <el-card class="filter-card" body-style="padding: 14px 18px">
      <div class="filter-row">
        <el-select v-model="filter.category" placeholder="全部分类" clearable style="width: 130px" @change="search"><el-option v-for="(v, k) in CATEGORY_LABEL" :key="k" :label="v" :value="k" /></el-select>
        <el-select v-model="filter.status" placeholder="全部状态" clearable style="width: 130px" @change="search"><el-option v-for="(v, k) in STATUS_TAG" :key="k" :label="v.text" :value="k" /></el-select>
        <el-date-picker v-model="filter.range" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" unlink-panels style="width: 240px" @change="search" />
        <el-input v-model="filter.keyword" placeholder="内容 / 联系方式" clearable style="width: 240px" @keyup.enter="search" @clear="search" />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <transition name="fade">
        <div v-if="selected.length" class="batch-bar">
          <span>已选 {{ selected.length }} 条</span>
          <el-button size="small" type="primary" plain @click="onBatch('REPLIED')">统一回复</el-button>
          <el-button size="small" plain @click="onBatch('PROCESSING')">置处理中</el-button>
          <el-button size="small" type="info" plain @click="onBatch('IGNORED')">批量忽略</el-button>
          <el-button size="small" link @click="selected = []">取消选择</el-button>
        </div>
      </transition>
    </el-card>

    <el-card class="table-card" body-style="padding: 0">
      <el-table v-loading="loading" :data="rows" row-key="id" @selection-change="(v: FeedbackItem[]) => (selected = v)">
        <template #empty><div class="empty"><div class="empty-title">没有符合条件的反馈</div><div class="empty-sub">换个筛选条件试试</div></div></template>
        <el-table-column type="selection" width="44" />
        <el-table-column label="反馈" min-width="360">
          <template #default="{ row }">
            <div class="fb-cell" @click="openItem(row)">
              <div class="fb-line"><el-tag size="small" :type="CATEGORY_TAG[row.category] || 'info'" effect="plain">{{ CATEGORY_LABEL[row.category] || row.category }}</el-tag><span class="fb-content">{{ row.content }}</span></div>
              <div class="fb-sub">#{{ row.id }} · {{ fmt(row.createdAt) }}<template v-if="row.taskId"> · 任务 <a class="link" @click.stop="router.push(`/task/${row.taskId}`)">#{{ row.taskId }}</a></template><template v-if="row.paragraphIdxs?.length"> · 申诉段 {{ row.paragraphIdxs.map((i: number) => i + 1).join('、') }}</template><template v-if="row.consentImprove"> · 已授权改进</template><template v-if="row.contact"> · {{ row.contact }}</template></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="STATUS_TAG[row.status as FeedbackStatus]?.type" size="small" effect="light">{{ STATUS_TAG[row.status as FeedbackStatus]?.text || row.status }}</el-tag></template></el-table-column>
        <el-table-column label="回复" min-width="200" show-overflow-tooltip><template #default="{ row }"><span v-if="row.handledReply" class="muted small">{{ row.handledReply }}</span><span v-else class="muted small">—</span></template></el-table-column>
        <el-table-column label="处理时间" width="150"><template #default="{ row }"><span class="muted">{{ fmt(row.handledAt) }}</span></template></el-table-column>
        <el-table-column label="操作" width="90" fixed="right"><template #default="{ row }"><el-button size="small" type="primary" link @click="openItem(row)">{{ row.status === 'REPLIED' || row.status === 'IGNORED' ? '查看' : '处理' }}</el-button></template></el-table-column>
      </el-table>
      <div class="pager-row"><span class="muted small">共 {{ total }} 条</span><el-pagination v-model:current-page="pageNum" v-model:page-size="pageSize" :total="total" :page-sizes="[10, 20, 50, 100]" layout="sizes, prev, pager, next" @size-change="load" @current-change="load" /></div>
    </el-card>

    <el-drawer v-model="drawer.open" size="560px" :with-header="false" destroy-on-close>
      <div v-if="drawer.item" class="dr">
        <div class="dr-head">
          <el-tag :type="CATEGORY_TAG[drawer.item.category] || 'info'" effect="plain">{{ CATEGORY_LABEL[drawer.item.category] }}</el-tag>
          <span class="muted small">#{{ drawer.item.id }} · {{ fmt(drawer.item.createdAt) }}<template v-if="drawer.item.userId"> · 用户 {{ drawer.item.userId }}</template></span>
          <el-tag :type="STATUS_TAG[drawer.item.status]?.type" size="small" effect="light" class="ml-auto">{{ STATUS_TAG[drawer.item.status]?.text }}</el-tag>
        </div>
        <div class="orig">
          <div class="orig-content">{{ drawer.item.content }}</div>
          <div v-if="drawer.item.contact" class="orig-meta">联系方式：{{ drawer.item.contact }}</div>
          <div v-if="drawer.item.taskId" class="orig-meta">关联任务 <a class="link" @click="router.push(`/task/${drawer.item!.taskId}`)">#{{ drawer.item.taskId }}</a><template v-if="drawer.item.paragraphIdxs?.length"> · 申诉段：{{ drawer.item.paragraphIdxs.map((i: number) => i + 1).join('、') }}</template><template v-if="drawer.item.consentImprove"> · 已授权用于评测</template></div>
        </div>

        <div v-if="drawer.item.category === 'appeal' && drawer.item.paragraphIdxs?.length" v-loading="drawer.samplesLoading" class="samples">
          <div class="sec-title">段级复核<span class="muted small">结论只进误判样本池，不改用户报告</span></div>
          <div v-for="s in drawer.samples" :key="s.id" class="sample">
            <div class="sample-head"><span class="sample-tag">第 {{ s.paragraphIdx + 1 }} 段 · 模型 {{ s.modelProb == null ? '—' : Math.round(Number(s.modelProb) * 100) + '%' }} · {{ s.modelVersion }}</span><el-tag v-if="s.opsVerdict" size="small" :type="s.opsVerdict === 'confirm_fp' ? 'danger' : s.opsVerdict === 'confirm_tp' ? 'success' : 'info'">{{ VERDICT_LABEL[s.opsVerdict] }}</el-tag></div>
            <div class="sample-text">{{ s.text || '（用户未授权保留原文，只有哈希；复核请打开关联任务查看）' }}</div>
            <div class="sample-actions">
              <el-button size="small" :type="s.opsVerdict === 'confirm_fp' ? 'danger' : 'default'" @click="verdict(s, 'confirm_fp')">确认误判</el-button>
              <el-button size="small" :type="s.opsVerdict === 'confirm_tp' ? 'success' : 'default'" @click="verdict(s, 'confirm_tp')">确认是 AI</el-button>
              <el-button size="small" :type="s.opsVerdict === 'unsure' ? 'info' : 'default'" @click="verdict(s, 'unsure')">拿不准</el-button>
            </div>
          </div>
          <div v-if="!drawer.samplesLoading && !drawer.samples.length" class="muted small">样本池里没有这条申诉的段落（可能迁移 V0.3.0.006 未跑）</div>
        </div>

        <div class="sec-title">处置</div>
        <el-radio-group v-model="drawer.status"><el-radio value="REPLIED">已回复</el-radio><el-radio value="PROCESSING">处理中</el-radio><el-radio value="IGNORED">已忽略</el-radio></el-radio-group>
        <div class="quick"><span class="muted small">快捷模板：</span><el-button v-for="q in QUICK_REPLIES" :key="q.t" size="small" round @click="useQuick(q.c)">{{ q.t }}</el-button></div>
        <el-input v-model="drawer.reply" type="textarea" :rows="5" maxlength="2000" show-word-limit placeholder="回复内容（已回复状态必填），用户会在「我的反馈」看到" />
        <div class="dr-foot">
          <span v-if="drawerDone" class="muted small">已于 {{ fmt(drawer.item.handledAt) }} 处理，可再次编辑</span>
          <span class="ml-auto" />
          <el-button @click="drawer.open = false">取消</el-button>
          <el-button type="primary" :loading="drawer.submitting" @click="submit">保存</el-button>
        </div>
      </div>
    </el-drawer>
  </template>

  <!-- ================= 误判样本池 ================= -->
  <template v-else>
    <div class="kpi-row four">
      <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">待复核</div><div class="kpi-value warn">{{ sampleStats.pending }}</div></el-card>
      <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">确认误判</div><div class="kpi-value bad">{{ sampleStats.confirm_fp }}</div></el-card>
      <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">确认是 AI</div><div class="kpi-value ok">{{ sampleStats.confirm_tp }}</div></el-card>
      <el-card class="kpi static" body-style="padding: 14px 16px"><div class="kpi-label">拿不准</div><div class="kpi-value">{{ sampleStats.unsure }}</div></el-card>
    </div>
    <el-card class="filter-card" body-style="padding: 14px 18px">
      <div class="filter-row">
        <el-select v-model="sf.verdict" placeholder="全部结论" clearable style="width: 140px" @change="loadSamples"><el-option label="待复核" value="pending" /><el-option label="确认误判" value="confirm_fp" /><el-option label="确认是 AI" value="confirm_tp" /><el-option label="拿不准" value="unsure" /></el-select>
        <el-select v-model="sf.days" style="width: 120px" @change="loadSamples"><el-option label="近 30 天" :value="30" /><el-option label="近 90 天" :value="90" /><el-option label="近 365 天" :value="365" /></el-select>
        <el-button @click="loadSamples">刷新</el-button>
        <span class="flex-1" />
        <a :href="hardSampleExportUrl()" target="_blank" class="el-button">导出已复核 JSONL</a>
      </div>
    </el-card>
    <el-card class="table-card" body-style="padding: 0">
      <el-table v-loading="samplesLoading" :data="samples" empty-text="样本池为空">
        <el-table-column label="段落" width="110"><template #default="{ row }">任务 <a class="link" @click="router.push(`/task/${row.taskId}`)">#{{ row.taskId }}</a> · 段 {{ row.paragraphIdx + 1 }}</template></el-table-column>
        <el-table-column label="文本" min-width="360"><template #default="{ row }"><span v-if="row.text" class="sample-cell">{{ row.text }}</span><span v-else class="muted small">未授权保留原文（哈希 {{ row.textSha256.slice(0, 10) }}…）</span></template></el-table-column>
        <el-table-column label="模型" width="110" align="right"><template #default="{ row }">{{ row.modelProb == null ? '—' : Math.round(Number(row.modelProb) * 100) + '%' }}<div class="cell-sub">{{ row.modelVersion }}</div></template></el-table-column>
        <el-table-column label="结论" width="110"><template #default="{ row }"><el-tag v-if="row.opsVerdict" size="small" :type="row.opsVerdict === 'confirm_fp' ? 'danger' : row.opsVerdict === 'confirm_tp' ? 'success' : 'info'">{{ VERDICT_LABEL[row.opsVerdict as HardSampleVerdict] }}</el-tag><el-tag v-else size="small" type="warning">待复核</el-tag></template></el-table-column>
        <el-table-column label="复核" width="230"><template #default="{ row }"><el-button size="small" link type="danger" @click="verdict(row, 'confirm_fp')">误判</el-button><el-button size="small" link type="success" @click="verdict(row, 'confirm_tp')">是 AI</el-button><el-button size="small" link @click="verdict(row, 'unsure')">拿不准</el-button></template></el-table-column>
        <el-table-column label="入池" width="140"><template #default="{ row }"><span class="muted small">{{ fmt(row.createdAt) }}</span></template></el-table-column>
      </el-table>
    </el-card>
  </template>
</template>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.page-title { font-size: 22px; font-weight: 700; letter-spacing: -0.4px; } .page-sub { font-size: 13px; color: var(--label-secondary); margin-top: 4px; }
.kpi-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 14px; } .kpi-row.four { grid-template-columns: repeat(4, 1fr); }
.kpi { cursor: pointer; border: 1px solid transparent; transition: border-color .15s, transform .15s; } .kpi:hover:not(.static) { transform: translateY(-1px); } .kpi.on { border-color: var(--system-blue); } .kpi.static { cursor: default; }
.kpi-label { font-size: 12px; color: var(--label-secondary); } .kpi-value { font-size: 26px; font-weight: 700; letter-spacing: -0.5px; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi-value.ok { color: #1B7F3E; } .kpi-value.bad { color: #C62A22; } .kpi-value.warn { color: #B26200; } .kpi-foot { font-size: 11px; color: var(--label-tertiary); margin-top: 6px; min-height: 14px; }
.filter-card { margin-bottom: 12px; } .filter-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; } .flex-1 { flex: 1; }
.batch-bar { display: flex; align-items: center; gap: 10px; margin-top: 12px; padding: 8px 12px; border-radius: 10px; background: rgba(0, 122, 255, 0.07); font-size: 13px; }
.fade-enter-active, .fade-leave-active { transition: opacity .15s; } .fade-enter-from, .fade-leave-to { opacity: 0; }
.table-card :deep(.el-table) { --el-table-header-bg-color: #FAFBFC; }
.fb-cell { cursor: pointer; } .fb-line { display: flex; align-items: center; gap: 8px; min-width: 0; } .fb-content { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .fb-cell:hover .fb-content { color: var(--system-blue); }
.fb-sub { font-size: 12px; color: var(--label-secondary); margin-top: 2px; }
.link { color: var(--system-blue); cursor: pointer; } .muted { color: var(--label-secondary); } .small { font-size: 12px; } .ml-auto { margin-left: auto; }
.cell-sub { font-size: 11px; color: var(--label-tertiary); } .sample-cell { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: 13px; }
.empty { padding: 36px 0; } .empty-title { font-weight: 600; color: var(--label); } .empty-sub { font-size: 12px; color: var(--label-tertiary); margin-top: 4px; }
.pager-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; }
.dr { display: flex; flex-direction: column; gap: 14px; } .dr-head { display: flex; align-items: center; gap: 10px; }
.orig { background: #F2F2F7; border-radius: 10px; padding: 14px; font-size: 14px; } .orig-content { white-space: pre-wrap; line-height: 1.6; } .orig-meta { margin-top: 8px; font-size: 12px; color: var(--label-secondary); }
.sec-title { font-size: 12px; font-weight: 600; color: var(--label-secondary); text-transform: uppercase; letter-spacing: .5px; display: flex; gap: 10px; align-items: center; }
.samples { display: flex; flex-direction: column; gap: 10px; }
.sample { border: 1px solid var(--label-quaternary); border-radius: 10px; padding: 10px 12px; } .sample-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; } .sample-tag { font-size: 12px; color: #C62A22; font-weight: 600; }
.sample-text { font-size: 13px; white-space: pre-wrap; max-height: 120px; overflow-y: auto; margin-bottom: 8px; line-height: 1.6; } .sample-actions { display: flex; gap: 6px; }
.quick { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.dr-foot { display: flex; align-items: center; gap: 8px; }
@media (max-width: 1200px) { .kpi-row { grid-template-columns: repeat(3, 1fr); } }
</style>
