<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAssistantStats, listKnowledgeGaps, getKnowledgeGapDraft,
  listKnowledge, getKnowledge, createKnowledge, updateKnowledge, setKnowledgeEnabled, reloadKnowledge,
  listAssistantConversations, getAssistantConversation, addQualityNote, getQualityStats,
  type AssistantStats, type KnowledgeGap, type KnowledgeChunkRow, type KnowledgeChunkPayload, type ReloadResult,
  type ConversationRow, type ConversationDetail, type QualityTag,
} from '@/api/admin'

/**
 * 助手运营 · 增长闭环 P0
 * 三个 tab：概览（assistant_log 聚合）/ 知识缺口（低分问题 → 转成知识）/ 知识库（knowledge_chunk 编辑 + 热加载）
 */

const tab = ref<'stats' | 'gaps' | 'kb' | 'qa'>('stats')

const INTENT_LABEL: Record<string, string> = {
  explain: '解释报告', policy: '政策红线', guide: '写作指导', appeal: '申诉', rewrite_request: '要求改写',
  history: '历史记录', chitchat: '闲聊', other: '其它', ghostwrite: '代写(拦截)', bypass: '绕过检测(拦截)',
  appeal_fabricate: '编申诉(拦截)', unknown: '未知',
}
const pct = (v: number | null | undefined) => (v == null ? '—' : (v * 100).toFixed(1) + '%')

/* ==================== 概览 ==================== */

const statsDays = ref(7)
const threshold = ref(1.0)
const stats = ref<AssistantStats | null>(null)
const statsLoading = ref(false)

async function loadStats() {
  statsLoading.value = true
  try { stats.value = await getAssistantStats(statsDays.value, threshold.value) }
  finally { statsLoading.value = false }
}

/* ==================== 知识缺口 ==================== */

const gapFilter = reactive({ days: 14, limit: 100 })
const gaps = ref<KnowledgeGap[]>([])
const gapsLoading = ref(false)

async function loadGaps() {
  gapsLoading.value = true
  try { gaps.value = await listKnowledgeGaps({ ...gapFilter, threshold: threshold.value }) }
  finally { gapsLoading.value = false }
}

/* ==================== 知识库 ==================== */

const kbFilter = reactive<{ doc: string; keyword: string; enabled: '' | 'true' | 'false' }>({ doc: '', keyword: '', enabled: '' })
const chunks = ref<KnowledgeChunkRow[]>([])
const kbLoading = ref(false)
const reloading = ref(false)

async function loadKb() {
  kbLoading.value = true
  try {
    chunks.value = await listKnowledge({
      doc: kbFilter.doc || undefined,
      keyword: kbFilter.keyword || undefined,
      enabled: kbFilter.enabled === '' ? undefined : kbFilter.enabled === 'true',
    })
  } finally { kbLoading.value = false }
}

function reportReload(r: ReloadResult | undefined, prefix: string) {
  if (!r) return ElMessage.success(prefix)
  if (r.ok === false) ElMessage.warning(`${prefix}，但推理服务未重载：${r.error || ''}`)
  else ElMessage.success(`${prefix}，已热加载 ${r.chunks ?? '?'} 块`)
}

async function onReload() {
  reloading.value = true
  try { reportReload(await reloadKnowledge(), '重载完成') }
  finally { reloading.value = false }
}

async function onToggle(row: KnowledgeChunkRow, enabled: boolean) {
  try {
    const r = await setKnowledgeEnabled(row.id, enabled)
    row.enabled = enabled
    reportReload(r, enabled ? '已上线' : '已下线')
  } catch { /* client.ts 已弹错误 */ }
}

/* ==================== 编辑弹窗（新增 / 编辑 / 转成知识共用） ==================== */

const editOpen = ref(false)
const editId = ref<number | null>(null)
const form = reactive<KnowledgeChunkPayload & { kbTopRef?: string | null }>({ doc: 'ops-faq', title: '', tags: '', body: '', enabled: true })
const saving = ref(false)
const dialogTitle = ref('新增知识块')

function resetForm(p?: Partial<typeof form>) {
  Object.assign(form, { doc: 'ops-faq', title: '', tags: '', body: '', enabled: true, sortOrder: undefined, fromLogId: undefined, kbTopRef: null }, p)
}

function openCreate() {
  editId.value = null
  dialogTitle.value = '新增知识块'
  resetForm()
  editOpen.value = true
}

async function openEdit(row: KnowledgeChunkRow) {
  const d = await getKnowledge(row.id)
  editId.value = d.id
  dialogTitle.value = `编辑 · ${d.doc} › ${d.title}`
  resetForm({ doc: d.doc, title: d.title, tags: d.tags, body: d.body, sortOrder: d.sortOrder, enabled: d.enabled })
  editOpen.value = true
}

async function openFromGap(gap: KnowledgeGap) {
  const d = await getKnowledgeGapDraft(gap.id)
  editId.value = null
  dialogTitle.value = '转成知识'
  resetForm({ ...d })
  editOpen.value = true
}

async function save() {
  if (!form.title.trim() || !form.body.trim()) return ElMessage.warning('标题和正文不能为空')
  saving.value = true
  try {
    const payload: KnowledgeChunkPayload = {
      doc: form.doc, title: form.title.trim(), tags: form.tags, body: form.body.trim(),
      sortOrder: form.sortOrder, enabled: form.enabled, fromLogId: form.fromLogId,
    }
    const r = editId.value == null ? await createKnowledge(payload) : await updateKnowledge(editId.value, payload)
    reportReload(r.reload, editId.value == null ? '已入库' : '已保存')
    editOpen.value = false
    if (tab.value === 'kb') loadKb()
    if (tab.value === 'gaps') loadGaps()
  } finally { saving.value = false }
}

async function confirmReloadAll() {
  await ElMessageBox.confirm('重新从 knowledge_chunk 全量加载到推理服务内存，几秒内完成。继续？', '热加载', { type: 'info' })
  onReload()
}

/* ==================== 对话质检 ==================== */

const qaFilter = reactive({ days: 14, boundaryOnly: false, limit: 50 })
const convs = ref<ConversationRow[]>([])
const convsLoading = ref(false)
const qaStats = ref<{ total: number; tags: Record<string, number>; avgScore: number | null } | null>(null)
const QA_TAG: Record<QualityTag, { text: string; type: 'success' | 'danger' | 'warning' | 'info' | 'primary'; action: string }> = {
  good:       { text: '答得好',     type: 'success', action: '无' },
  wrong_fact: { text: '答错了',     type: 'danger',  action: '查工具返回 → 修工具或知识' },
  off_point:  { text: '没答到点上', type: 'warning', action: '补知识块' },
  boundary:   { text: '越界了',     type: 'danger',  action: '收紧边界规则' },
  tone:       { text: '太啰嗦/太冷', type: 'info',    action: '调提示词' },
}

async function loadConvs() {
  convsLoading.value = true
  try {
    const [rows, st] = await Promise.all([listAssistantConversations(qaFilter), getQualityStats(30)])
    convs.value = rows
    qaStats.value = st
  } finally { convsLoading.value = false }
}

const convOpen = ref(false)
const convDetail = ref<ConversationDetail | null>(null)
const convLoading = ref(false)
const noteTag = ref<QualityTag>('good')
const noteScore = ref<number>(4)
const noteText = ref('')
const noteLogId = ref<number | undefined>(undefined)
const noteSaving = ref(false)

async function openConv(row: ConversationRow) {
  convOpen.value = true
  convLoading.value = true
  convDetail.value = null
  noteTag.value = 'good'; noteScore.value = 4; noteText.value = ''; noteLogId.value = undefined
  try { convDetail.value = await getAssistantConversation(row.conversationId) }
  finally { convLoading.value = false }
}

async function saveNote() {
  if (!convDetail.value) return
  noteSaving.value = true
  try {
    await addQualityNote({
      conversationId: convDetail.value.conversation.conversationId,
      logId: noteLogId.value,
      score: noteScore.value,
      tag: noteTag.value,
      note: noteText.value.trim() || undefined,
    })
    ElMessage.success(`已标注：${QA_TAG[noteTag.value].text} → ${QA_TAG[noteTag.value].action}`)
    convDetail.value = await getAssistantConversation(convDetail.value.conversation.conversationId)
    const row = convs.value.find((c) => c.conversationId === convDetail.value!.conversation.conversationId)
    if (row) row.noteCount += 1
    noteText.value = ''
  } finally { noteSaving.value = false }
}

function fmtTs(ts?: number) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function onTab(name: string | number) {
  if (name === 'stats' && !stats.value) loadStats()
  if (name === 'gaps' && !gaps.value.length) loadGaps()
  if (name === 'kb' && !chunks.value.length) loadKb()
  if (name === 'qa' && !convs.value.length) loadConvs()
}

onMounted(loadStats)
</script>

<template>
  <el-tabs v-model="tab" class="aa-tabs" @tab-change="onTab">
    <!-- ================= 概览 ================= -->
    <el-tab-pane label="概览" name="stats">
      <el-card class="filter-card">
        <div class="filter-row">
          <span class="muted">统计窗口</span>
          <el-select v-model="statsDays" style="width: 110px" @change="loadStats">
            <el-option label="近 7 天" :value="7" /><el-option label="近 14 天" :value="14" /><el-option label="近 30 天" :value="30" />
          </el-select>
          <span class="muted">知识命中阈值</span>
          <el-input-number v-model="threshold" :min="0" :max="20" :step="0.1" :precision="1" size="default" style="width: 120px" @change="loadStats" />
          <el-button @click="loadStats" :loading="statsLoading">刷新</el-button>
        </div>
      </el-card>

      <div v-if="stats" class="kpi-row">
        <el-card class="kpi-card"><div class="kpi-label">对话轮次</div><div class="kpi-value">{{ stats.conversations }}</div></el-card>
        <el-card class="kpi-card"><div class="kpi-label">对话用户</div><div class="kpi-value">{{ stats.users }}</div></el-card>
        <el-card class="kpi-card"><div class="kpi-label">知识命中率</div><div class="kpi-value">{{ pct(stats.kbHitRate) }}</div><div class="kpi-sub">样本 {{ stats.kbSample }}</div></el-card>
        <el-card class="kpi-card"><div class="kpi-label">越界率</div><div class="kpi-value" :class="{ danger: (stats.boundaryRate || 0) > 0 }">{{ pct(stats.boundaryRate) }}</div></el-card>
        <el-card class="kpi-card"><div class="kpi-label">工具失败率</div><div class="kpi-value">{{ pct(stats.toolFailedRate) }}</div></el-card>
      </div>

      <div v-if="stats" class="mid-row">
        <el-card>
          <template #header><div class="card-title">意图分布</div></template>
          <el-table :data="Object.entries(stats.intents).map(([k, v]) => ({ k, v })).sort((a, b) => b.v - a.v)" size="small">
            <el-table-column label="意图" min-width="160"><template #default="{ row }">{{ INTENT_LABEL[row.k] || row.k }}</template></el-table-column>
            <el-table-column prop="v" label="次数" width="100" />
            <el-table-column label="占比" width="100"><template #default="{ row }">{{ pct(stats!.conversations ? row.v / stats!.conversations : null) }}</template></el-table-column>
          </el-table>
        </el-card>
        <el-card>
          <template #header><div class="card-title">越界类型 / 用量</div></template>
          <div class="kv"><span>越界类型</span><span>{{ Object.keys(stats.boundaryTypes).length ? Object.entries(stats.boundaryTypes).map(([k, v]) => `${INTENT_LABEL[k] || k} ${v}`).join(' · ') : '无' }}</span></div>
          <div class="kv"><span>错误率</span><span>{{ pct(stats.errorRate) }}</span></div>
          <div class="kv"><span>prompt tokens</span><span>{{ stats.promptTokens.toLocaleString() }}</span></div>
          <div class="kv"><span>completion tokens</span><span>{{ stats.completionTokens.toLocaleString() }}</span></div>
          <div class="hint">口径见 docs/design/202610-assistant-growth-loop-plan.md §7。知识命中率分母只含「政策 / 指导 / 其它」三类意图。</div>
        </el-card>
      </div>
    </el-tab-pane>

    <!-- ================= 知识缺口 ================= -->
    <el-tab-pane label="知识缺口" name="gaps">
      <el-card class="filter-card">
        <div class="filter-row">
          <el-select v-model="gapFilter.days" style="width: 110px">
            <el-option label="近 7 天" :value="7" /><el-option label="近 14 天" :value="14" /><el-option label="近 30 天" :value="30" />
          </el-select>
          <span class="muted">阈值</span>
          <el-input-number v-model="threshold" :min="0" :max="20" :step="0.1" :precision="1" style="width: 120px" />
          <el-button type="primary" @click="loadGaps" :loading="gapsLoading">查询</el-button>
          <span class="hint">该走知识库的意图里，top-1 BM25 分数低于阈值或未检索到的问题。点「转成知识」预填草稿。</span>
        </div>
      </el-card>
      <el-card class="table-card">
        <el-table v-loading="gapsLoading" :data="gaps" empty-text="窗口内没有候选缺口">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="question" label="用户原问" min-width="320" show-overflow-tooltip />
          <el-table-column label="意图" width="110"><template #default="{ row }">{{ INTENT_LABEL[row.intent] || row.intent }}</template></el-table-column>
          <el-table-column label="命中分" width="90"><template #default="{ row }">{{ row.kbTopScore == null ? '未检索' : row.kbTopScore }}</template></el-table-column>
          <el-table-column prop="kbTopRef" label="当时命中块" min-width="220" show-overflow-tooltip><template #default="{ row }">{{ row.kbTopRef || '—' }}</template></el-table-column>
          <el-table-column prop="createdAt" label="时间" width="170" />
          <el-table-column label="操作" width="110" fixed="right">
            <template #default="{ row }"><el-button size="small" type="primary" link @click="openFromGap(row)">转成知识</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-tab-pane>

    <!-- ================= 知识库 ================= -->
    <el-tab-pane label="知识库" name="kb">
      <el-card class="filter-card">
        <div class="filter-row">
          <el-input v-model="kbFilter.doc" placeholder="文档，如 03-policy-thresholds / ops-faq" clearable style="width: 240px" @keyup.enter="loadKb" />
          <el-input v-model="kbFilter.keyword" placeholder="标题 / 正文关键词" clearable style="width: 220px" @keyup.enter="loadKb" />
          <el-select v-model="kbFilter.enabled" placeholder="状态" clearable style="width: 110px">
            <el-option label="已上线" value="true" /><el-option label="已下线" value="false" />
          </el-select>
          <el-button type="primary" @click="loadKb" :loading="kbLoading">查询</el-button>
          <el-button @click="openCreate">新增</el-button>
          <el-button :loading="reloading" @click="confirmReloadAll">热加载</el-button>
        </div>
      </el-card>
      <el-card class="table-card">
        <el-table v-loading="kbLoading" :data="chunks" empty-text="knowledge_chunk 为空：先跑 R__seed_knowledge_chunk.sql 入库">
          <el-table-column prop="doc" label="文档" width="190" />
          <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip />
          <el-table-column prop="bodyPreview" label="正文" min-width="320" show-overflow-tooltip />
          <el-table-column prop="tags" label="标签" width="140" show-overflow-tooltip />
          <el-table-column label="上线" width="80">
            <template #default="{ row }"><el-switch :model-value="row.enabled" size="small" @change="(v: boolean) => onToggle(row, v)" /></template>
          </el-table-column>
          <el-table-column prop="updatedAt" label="更新时间" width="170" />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }"><el-button size="small" type="primary" link @click="openEdit(row)">编辑</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-tab-pane>
    <!-- ================= 对话质检 ================= -->
    <el-tab-pane label="对话质检" name="qa">
      <el-card class="filter-card">
        <div class="filter-row">
          <el-select v-model="qaFilter.days" style="width: 110px">
            <el-option label="近 7 天" :value="7" /><el-option label="近 14 天" :value="14" /><el-option label="近 30 天" :value="30" />
          </el-select>
          <el-checkbox v-model="qaFilter.boundaryOnly">只看越界会话</el-checkbox>
          <el-button type="primary" @click="loadConvs" :loading="convsLoading">查询</el-button>
          <span v-if="qaStats" class="hint">
            近 30 天已标注 {{ qaStats.total }} 条，均分 {{ qaStats.avgScore ?? '—' }}；
            <template v-for="(v, k) in qaStats.tags" :key="k">{{ QA_TAG[k as QualityTag]?.text || k }} {{ v }} · </template>
          </span>
          <span class="hint">抽样规则：越界的全抽，其余按意图分层随机，每周 30 条。</span>
        </div>
      </el-card>
      <el-card class="table-card">
        <el-table v-loading="convsLoading" :data="convs" empty-text="窗口内没有会话（assistant_conversation 需 Python 配 ASSISTANT_KB_DB_* 且不配 ASSISTANT_REDIS_URL 才落库）">
          <el-table-column prop="title" label="首问" min-width="260" show-overflow-tooltip />
          <el-table-column label="任务" width="90"><template #default="{ row }">{{ row.taskId ? '#' + row.taskId : '—' }}</template></el-table-column>
          <el-table-column prop="turns" label="轮数" width="70" />
          <el-table-column label="越界" width="70"><template #default="{ row }"><el-tag v-if="row.boundaryCount" type="danger" size="small">{{ row.boundaryCount }}</el-tag><span v-else class="muted">0</span></template></el-table-column>
          <el-table-column label="意图" min-width="180"><template #default="{ row }">{{ row.intents.map((i: string) => INTENT_LABEL[i] || i).join(' · ') }}</template></el-table-column>
          <el-table-column prop="noteCount" label="已标注" width="80" />
          <el-table-column prop="updatedAt" label="最近" width="170" />
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }"><el-button size="small" type="primary" link @click="openConv(row)">质检</el-button></template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-tab-pane>
  </el-tabs>

  <!-- ================= 质检抽屉 ================= -->
  <el-drawer v-model="convOpen" size="560px" title="对话质检">
    <div v-loading="convLoading" class="qa">
      <template v-if="convDetail">
        <div class="qa-meta muted">
          会话 {{ convDetail.conversation.conversationId }} · 用户 {{ convDetail.conversation.userId ?? '匿名' }} · 任务 {{ convDetail.conversation.taskId ? '#' + convDetail.conversation.taskId : '无' }}
        </div>
        <div class="qa-msgs">
          <div v-for="(m, i) in convDetail.conversation.messages" :key="i" class="qa-msg" :class="m.role">
            <div class="qa-msg-head">{{ m.role === 'user' ? '用户' : '助手' }} <span class="muted">{{ fmtTs(m.ts) }}</span><el-tag v-if="m.blocked" size="small" type="danger">安全拦截</el-tag></div>
            <div class="qa-msg-body">{{ m.content }}</div>
          </div>
        </div>
        <div v-if="convDetail.logs.length" class="qa-logs">
          <div class="qa-sub">每轮审计</div>
          <div v-for="l in convDetail.logs" :key="l.id" class="qa-log" :class="{ picked: noteLogId === l.id }" @click="noteLogId = noteLogId === l.id ? undefined : l.id">
            <span class="muted">#{{ l.id }}</span> {{ INTENT_LABEL[l.intent] || l.intent }}
            <el-tag v-if="l.boundaryFlag" size="small" type="danger">{{ l.boundaryType }}</el-tag>
            <span class="muted"> · 工具 {{ l.tools || '无' }} · 知识 {{ l.kbTopScore ?? '—' }} · {{ l.latencyMs ?? '—' }}ms</span>
          </div>
          <div class="hint">点一轮可把标注落到该轮；不点即整段会话。</div>
        </div>
        <div v-if="convDetail.notes.length" class="qa-notes">
          <div class="qa-sub">已有标注</div>
          <div v-for="n in convDetail.notes" :key="n.id" class="qa-note">
            <el-tag size="small" :type="QA_TAG[n.tag]?.type">{{ QA_TAG[n.tag]?.text || n.tag }}</el-tag>
            <span v-if="n.score"> {{ n.score }} 分</span><span v-if="n.logId" class="muted"> · 第 #{{ n.logId }} 轮</span>
            <span v-if="n.note"> · {{ n.note }}</span><span class="muted"> · {{ n.createdAt }}</span>
          </div>
        </div>
        <div class="qa-form">
          <div class="qa-sub">新标注</div>
          <el-radio-group v-model="noteTag">
            <el-radio-button v-for="(v, k) in QA_TAG" :key="k" :value="k">{{ v.text }}</el-radio-button>
          </el-radio-group>
          <div class="qa-form-row">
            <span class="muted">评分</span><el-rate v-model="noteScore" :max="5" />
            <span class="hint">→ {{ QA_TAG[noteTag].action }}</span>
          </div>
          <el-input v-model="noteText" type="textarea" :rows="2" maxlength="500" placeholder="备注（可选）：哪里错、该补什么" />
          <el-button type="primary" :loading="noteSaving" @click="saveNote">保存标注</el-button>
        </div>
      </template>
    </div>
  </el-drawer>

  <!-- ================= 编辑弹窗 ================= -->
  <el-dialog v-model="editOpen" width="680" :title="dialogTitle" align-center>
    <el-form label-width="72px">
      <el-form-item label="文档"><el-input v-model="form.doc" placeholder="ops-faq" /></el-form-item>
      <el-form-item label="标题"><el-input v-model="form.title" maxlength="128" show-word-limit placeholder="一句话可搜，如「与查重的区别」" /></el-form-item>
      <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔，参与检索" /></el-form-item>
      <el-form-item label="正文">
        <el-input v-model="form.body" type="textarea" :rows="10" placeholder="平台官方口径。写清结论、依据、建议动作；不要写能直接复制进论文的句子。" />
      </el-form-item>
      <el-form-item v-if="form.kbTopRef" label="当时命中"><span class="muted">{{ form.kbTopRef }}</span></el-form-item>
      <el-form-item label="上线"><el-switch v-model="form.enabled" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editOpen = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存并热加载</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.table-card :deep(.el-card__body) { padding: 0; }
.muted { color: rgba(60,60,67,0.60); }
.hint { font-size: 12px; color: rgba(60,60,67,0.60); margin-top: 10px; line-height: 1.5; }

.kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 16px; }
.kpi-card { text-align: center; }
.kpi-label { font-size: 13px; color: rgba(60,60,67,0.60); }
.kpi-value { font-size: 30px; font-weight: 600; letter-spacing: -0.5px; margin-top: 6px; color: #1C1C1E; }
.kpi-value.danger { color: #C62A22; }
.kpi-sub { font-size: 12px; color: rgba(60,60,67,0.45); margin-top: 2px; }

.mid-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.qa { display: flex; flex-direction: column; gap: 14px; }
.qa-meta { font-size: 12px; }
.qa-sub { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.qa-msgs { display: flex; flex-direction: column; gap: 8px; max-height: 40vh; overflow-y: auto; background: var(--el-fill-color-lighter); padding: 10px; border-radius: 10px; }
.qa-msg { padding: 8px 10px; border-radius: 10px; background: #fff; font-size: 13px; }
.qa-msg.user { background: var(--el-color-primary-light-9); }
.qa-msg-head { font-size: 12px; font-weight: 600; margin-bottom: 4px; display: flex; gap: 8px; align-items: center; }
.qa-msg-body { white-space: pre-wrap; line-height: 1.5; }
.qa-log { font-size: 12px; padding: 4px 8px; border-radius: 6px; cursor: pointer; }
.qa-log:hover { background: var(--el-fill-color); }
.qa-log.picked { background: var(--el-color-primary-light-8); }
.qa-note { font-size: 12px; padding: 4px 0; }
.qa-form { display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--el-border-color-lighter); padding-top: 12px; }
.qa-form-row { display: flex; align-items: center; gap: 10px; }
.card-title { font-weight: 600; }
.kv { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(60,60,67,0.08); font-size: 14px; }
.kv span:first-child { color: rgba(60,60,67,0.60); }
</style>
