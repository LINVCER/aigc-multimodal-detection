<script setup lang="ts">
import { ref, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import AssistantAnalysisCard from '@/components/AssistantAnalysisCard.vue'
import { renderMarkdown } from '@/utils/markdown'
import { chatStream, getQuickPrompts, listConversations, getConversation, deleteConversation, type ChatHandle } from '@/api/assistant'
import { listTasks, getTaskDetail } from '@/api/detect'
import { submitFeedback } from '@/api/feedback'
import type { DetectTask, TaskDetail } from '@/api/types'

/**
 * 论文检测助手 · 右侧抽屉（Web 端）
 * 布局按 docs/design/202610-assistant-chat-ui-redesign.md §2.2 分四区：
 *   头部（身份 + 历史/新对话/关闭）→ 报告选择（紧凑下拉）→ 上下文卡（绑定报告时）→ 消息流 + 输入
 * 数据来源不变：listTasks 选报告、getTaskDetail 出段落 chips、chatStream 走 SSE
 */

interface ToolChip { name: string; label: string; status: 'running' | 'done' | 'failed' }
interface AnalysisCard { name: string; data: any }
interface Msg {
  role: 'user' | 'assistant'
  text: string
  tools?: ToolChip[]
  /** 结构化分析卡（tool_result.card） */
  cards?: AnalysisCard[]
  error?: string | null
  streaming?: boolean
  /** 点赞 / 点踩（落 user_feedback，category=suggestion） */
  rating?: 'up' | 'down'
}

/** 工具调用图标（方案 §3.2） */
const TOOL_ICON: Record<string, string> = {
  get_task_detail: '📊', list_my_tasks: '🗂', explain_paragraph: '🔍', detect_text: '🧪',
  get_threshold_policy: '📏', search_knowledge: '📚', create_appeal: '✍️',
}
/** 工具完成后的短标签：「已读取报告」而不是「正在读取检测报告…」 */
const TOOL_DONE: Record<string, string> = {
  get_task_detail: '已读取报告', list_my_tasks: '已查看记录', explain_paragraph: '已分析段落', detect_text: '已检测',
  get_threshold_policy: '已查阈值', search_knowledge: '已查资料', create_appeal: '已提交申诉',
}

const props = defineProps<{
  modelValue: boolean
  taskId?: number
  /** 打开时自动追问的段落（「为什么这段像 AI」直达） */
  paragraphIdx?: number | null
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const messages = ref<Msg[]>([])
const input = ref('')
const conversationId = ref('')
const streaming = ref(false)
const welcome = ref('')
const prompts = ref<string[]>([])
const listEl = ref<HTMLElement | null>(null)
let handle: ChatHandle | null = null
let pendingParagraph: number | null = null

// ---- 报告上下文 ----
const activeTaskId = ref<number | undefined>(undefined)   // undefined = 通用咨询
const taskOptions = ref<DetectTask[]>([])
const taskDetail = ref<TaskDetail | null>(null)
const loadingTasks = ref(false)

const activeTask = computed(() => taskOptions.value.find((t) => t.id === activeTaskId.value))
const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
const showQuick = computed(() => messages.value.length === 0 && prompts.value.length > 0)

/** 绑定报告后，供「分析原因」用的高风险段落（正文、≥40%，按概率倒序取前 6） */
const riskParagraphs = computed(() => {
  const ps = taskDetail.value?.paragraphs || []
  return ps
    .filter((p) => !p.excluded && (p.calibratedProb ?? 0) >= 0.4)
    .sort((a, b) => (b.calibratedProb ?? 0) - (a.calibratedProb ?? 0))
    .slice(0, 6)
})
const bodyCount = computed(() => (taskDetail.value?.paragraphs || []).filter((p) => !p.excluded).length)

/** 上下文卡的达标徽章：沿用报告页 summaryColor 逻辑（绿 / 橙 / 红） */
const taskBadge = computed(() => {
  const t = activeTask.value
  if (!t || t.aiRate == null) return null
  const diff = t.aiRate - t.threshold
  if (diff <= 0) return { text: '达标', cls: 'ok' }
  return { text: `超标 ${diff.toFixed(1)}pp`, cls: diff <= t.threshold * 0.5 ? 'warn' : 'bad' }
})

function pct(prob: number | null | undefined): string {
  return `${((prob ?? 0) * 100).toFixed(0)}%`
}

// ---- 本地持久化：切换窗口/刷新不丢（后端 MySQL 仍作 7 天跨设备备份）----
const LS_KEY = 'paperaigc_chat_state'

interface LocalChatState {
  conversationId: string
  activeTaskId?: number
  messages: Msg[]
}

function persist() {
  try {
    const state: LocalChatState = { conversationId: conversationId.value, activeTaskId: activeTaskId.value, messages: messages.value }
    localStorage.setItem(LS_KEY, JSON.stringify(state))
  } catch { /* 存储满 / 隐私模式，忽略 */ }
}

function restore() {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return
    const state = JSON.parse(raw) as LocalChatState
    conversationId.value = state.conversationId || ''
    activeTaskId.value = state.activeTaskId
    messages.value = state.messages || []
  } catch { /* 解析失败忽略 */ }
}

onBeforeUnmount(() => {
  handle?.abort()
  persist()
})

async function loadTasks() {
  if (loadingTasks.value) return
  loadingTasks.value = true
  try {
    const page = await listTasks({ pageNum: 1, pageSize: 20 })
    taskOptions.value = (page.rows || []).filter((t) => t.status === 'DONE')
  } catch {
    taskOptions.value = []
  } finally {
    loadingTasks.value = false
  }
}

async function refreshPrompts(taskId?: number) {
  try {
    const qp = await getQuickPrompts(taskId)
    welcome.value = qp.welcome
    prompts.value = qp.prompts || []
  } catch {
    welcome.value = '嗨，我是小白。检测结果看不懂、不知道怎么改，都可以直接问我。'
  }
}

/** 切换 / 绑定报告：换上下文即开新对话，并重拉快捷问题与段落 */
async function selectTask(id?: number) {
  if (streaming.value) handle?.abort()
  activeTaskId.value = id
  conversationId.value = ''
  messages.value = []
  taskDetail.value = null
  pendingParagraph = null
  persist()
  await refreshPrompts(id)
  if (id != null) {
    try { taskDetail.value = await getTaskDetail(id) } catch { taskDetail.value = null }
  }
}

function onTaskChange(v: number | undefined) {
  // el-select 清除时可能回传 '' 或 undefined，统一归一为「通用咨询」
  selectTask(v || undefined)
}

watch(() => props.modelValue, async (open) => {
  if (!open) return
  // 1) 恢复本地暂存会话（路由切换导致组件卸载后，重新挂载时 messages 为空）
  if (messages.value.length === 0 && !conversationId.value) restore()
  const restored = messages.value.length > 0
  if (taskOptions.value.length === 0) await loadTasks()
  // 2) 恢复的会话绑定了报告 → 加载段落
  if (activeTaskId.value != null && taskDetail.value == null) {
    try { taskDetail.value = await getTaskDetail(activeTaskId.value) } catch { taskDetail.value = null }
  }
  // 3) 只有「无历史会话」时才用当前页面 taskId 初始化；有历史会话则尊重它，不清空
  if (!restored && props.taskId != null && props.taskId !== activeTaskId.value) {
    await selectTask(props.taskId)
  } else if (!welcome.value) {
    await refreshPrompts(activeTaskId.value)
  }
  // 4) 「为什么这段像 AI」直达：仅无历史会话时
  if (props.paragraphIdx != null && !restored) {
    pendingParagraph = props.paragraphIdx
    send(`第 ${props.paragraphIdx + 1} 段为什么会被判成像 AI？`)
  }
})

function scrollBottom() {
  nextTick(() => { if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight })
}

function onSend() {
  if (!canSend.value) return
  const t = input.value.trim()
  input.value = ''
  send(t)
}

function send(text: string) {
  if (streaming.value) return
  messages.value.push({ role: 'user', text })
  const reply: Msg = { role: 'assistant', text: '', tools: [], error: null, streaming: true }
  messages.value.push(reply)
  streaming.value = true
  scrollBottom()

  const userIdRaw = localStorage.getItem('user_id')
  handle = chatStream({
    message: text,
    conversationId: conversationId.value || undefined,
    taskId: activeTaskId.value,
    paragraphIdx: pendingParagraph ?? undefined,
    userId: userIdRaw ? Number(userIdRaw) : undefined,
    clientContext: { platform: 'web', page: 'AssistantDrawer' },
  }, {
    onEvent: (event, data) => {
      switch (event) {
        case 'meta':
          if (data?.conversationId) conversationId.value = data.conversationId
          break
        case 'token':
          reply.text += data?.delta || ''
          scrollBottom()
          break
        case 'tool_call':
          reply.tools!.push({ name: data?.name, label: data?.label || data?.name, status: 'running' })
          break
        case 'tool_result': {
          const t = reply.tools!.find((x) => x.name === data?.name && x.status === 'running')
          if (t) t.status = data?.ok === false ? 'failed' : 'done'
          if (data?.card) (reply.cards ||= []).push({ name: data.name, data: data.card })
          break
        }
        case 'error':
          reply.error = data?.message || '助手出了点问题，稍后再试'
          break
      }
    },
    onError: (err) => { reply.error = err.message || '网络异常' },
  })
  pendingParagraph = null

  handle.done.finally(() => {
    reply.streaming = false
    streaming.value = false
    if (!reply.text && !reply.error) reply.error = '助手没有返回内容，再试一次'
    persist()
    scrollBottom()
  })
}

/** 一键「分析原因」：追问某个具体段落 */
function analyzeParagraph(idx: number) {
  pendingParagraph = idx
  send(`第 ${idx + 1} 段为什么会被判成像 AI？`)
}

/** 一键「分析原因」：整体归因 + 优先级 */
function analyzeOverall() {
  const d = taskDetail.value
  if (!d) return
  const rate = d.aiRate != null ? `${d.aiRate.toFixed(1)}%` : '未知'
  send(`这份报告整体 AI 率是 ${rate}（红线 ${d.threshold}%）。帮我分析一下可能的原因，以及哪几段最该先改。`)
}

function onStop() { handle?.abort() }

function onRetry(idx: number) {
  for (let i = idx - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      const text = messages.value[i].text
      messages.value.splice(i, 2)
      send(text)
      return
    }
  }
}

function onNewChat() {
  handle?.abort()
  conversationId.value = ''
  messages.value = []
  streaming.value = false
  pendingParagraph = null
  persist()
}

// ---- 复制 + 点赞点踩（方案 §3.4）----
async function copyAnswer(m: Msg) {
  try {
    await navigator.clipboard.writeText(m.text)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择文字')
  }
}

/** 点赞 / 点踩落 user_feedback（category=suggestion），内容带问答摘要供运营质检 */
async function rateAnswer(idx: number, rating: 'up' | 'down') {
  const m = messages.value[idx]
  if (!m || m.rating) return
  const q = [...messages.value.slice(0, idx)].reverse().find((x) => x.role === 'user')?.text || ''
  m.rating = rating
  persist()
  try {
    const userIdRaw = localStorage.getItem('user_id')
    await submitFeedback({
      category: 'suggestion',
      content: `[助手${rating === 'up' ? '点赞' : '点踩'}] 会话 ${conversationId.value || '-'}\n问：${q.slice(0, 300)}\n答：${m.text.slice(0, 600)}`,
      taskId: activeTaskId.value,
      userId: userIdRaw ? Number(userIdRaw) : undefined,
    })
    ElMessage.success(rating === 'up' ? '谢谢，已记录' : '已记录，我们会改进')
  } catch {
    // 未登录等情况：本地标记保留，不打扰用户
  }
}

// ---- 历史会话（聊天记录，后端保留 7 天）----
const showHistory = ref(false)
const historyList = ref<Array<{ conversationId: string; title: string; taskId?: number; updatedAt: number | string; turns: number }>>([])
const loadingHistory = ref(false)

async function openHistory() {
  showHistory.value = true
  await loadHistory()
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const userIdRaw = localStorage.getItem('user_id')
    historyList.value = await listConversations(userIdRaw ? Number(userIdRaw) : undefined, 30)
  } catch {
    historyList.value = []
  } finally {
    loadingHistory.value = false
  }
}

/** 恢复历史会话：加载消息 + 同步报告上下文 */
async function resumeConversation(c: { conversationId: string; taskId?: number }) {
  try {
    const detail = await getConversation(c.conversationId)
    conversationId.value = c.conversationId
    if (c.taskId != null && c.taskId !== activeTaskId.value) {
      activeTaskId.value = c.taskId
      taskDetail.value = null
      try { taskDetail.value = await getTaskDetail(c.taskId) } catch { taskDetail.value = null }
      await refreshPrompts(c.taskId)
    }
    messages.value = (detail.messages || [])
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role as 'user' | 'assistant', text: m.content, tools: [], error: null, streaming: false }))
    showHistory.value = false
    persist()
    scrollBottom()
  } catch { /* toast 由拦截器给 */ }
}

async function removeConversation(c: { conversationId: string }) {
  try {
    await deleteConversation(c.conversationId)
    historyList.value = historyList.value.filter((x) => x.conversationId !== c.conversationId)
    if (conversationId.value === c.conversationId) {
      conversationId.value = ''
      messages.value = []
    }
  } catch { /* 忽略 */ }
}

function formatTime(t: number | string): string {
  const ts = typeof t === 'number' ? t * 1000 : Date.parse(t)
  if (!ts || isNaN(ts)) return ''
  const diff = Date.now() - ts
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  return `${Math.floor(diff / 86_400_000)} 天前`
}
</script>

<template>
  <el-drawer v-model="visible" size="480px" :with-header="false" class="assistant-drawer">
    <div class="ad">
      <!-- ① 头部：只留身份 + 全局操作 -->
      <div class="ad-head">
        <div class="ad-title">
          <img class="ad-avatar" src="/xiaobai.gif" alt="小白" />
          <div class="ad-name">小白</div>
        </div>
        <div class="ad-head-actions">
          <el-tooltip content="历史对话" placement="bottom"><el-button link class="ad-icon-btn" @click="openHistory">🕘</el-button></el-tooltip>
          <el-tooltip content="新对话" placement="bottom"><el-button link class="ad-icon-btn" @click="onNewChat">✚</el-button></el-tooltip>
          <el-tooltip content="关闭" placement="bottom"><el-button link class="ad-icon-btn" @click="visible = false">✕</el-button></el-tooltip>
        </div>
      </div>

      <template v-if="!showHistory">
        <!-- ② 报告选择：一行紧凑下拉 -->
        <div class="ad-select-row">
          <el-select
            v-model="activeTaskId" class="ad-task-select" size="default"
            placeholder="通用咨询（选择报告可围绕它聊）" clearable :loading="loadingTasks" @change="onTaskChange"
          >
            <el-option v-for="t in taskOptions" :key="t.id" :value="t.id" :label="t.paperTitle">
              <span class="ad-opt-title">{{ t.paperTitle }}</span>
              <span class="ad-opt-rate" :class="{ over: t.aiRate != null && t.aiRate > t.threshold }">
                AI {{ t.aiRate != null ? t.aiRate.toFixed(0) + '%' : '—' }}
              </span>
            </el-option>
          </el-select>
        </div>

        <!-- ③ 上下文卡：绑定报告时才出现 -->
        <div v-if="activeTask" class="ad-ctx">
          <div class="ad-ctx-head">
            <span class="ad-ctx-icon">📄</span>
            <span class="ad-ctx-title" :title="activeTask.paperTitle">《{{ activeTask.paperTitle }}》</span>
            <span v-if="taskBadge" class="ad-ctx-badge" :class="taskBadge.cls">{{ taskBadge.cls === 'ok' ? '✓ ' : '' }}{{ taskBadge.text }}</span>
          </div>
          <div class="ad-ctx-meta">
            整体 AI <b>{{ activeTask.aiRate == null ? '—' : activeTask.aiRate.toFixed(1) + '%' }}</b>
            <span class="sep">·</span>红线 {{ activeTask.threshold }}%
            <span v-if="taskDetail" class="sep">·</span><span v-if="taskDetail">正文 {{ bodyCount }} 段</span>
          </div>
          <div v-if="taskDetail" class="ad-ctx-chips">
            <span class="ad-chip primary" @click="analyzeOverall">整体怎么看</span>
            <span v-for="p in riskParagraphs" :key="p.paragraphIdx" class="ad-chip" :class="(p.calibratedProb ?? 0) >= 0.7 ? 'red' : 'yellow'" @click="analyzeParagraph(p.paragraphIdx)">
              段 {{ p.paragraphIdx + 1 }} · {{ pct(p.calibratedProb) }}
            </span>
          </div>
        </div>

        <!-- ④ 消息流 -->
        <div ref="listEl" class="ad-list">
          <div class="ad-welcome">
            <img class="ad-avatar sm" src="/xiaobai.gif" alt="小白" />
            <div class="ad-welcome-text">{{ welcome }}</div>
          </div>

          <div v-if="showQuick" class="ad-quick">
            <span v-for="q in prompts" :key="q" class="ad-chip" @click="send(q)">{{ q }}</span>
          </div>

          <div v-for="(m, i) in messages" :key="i" class="ad-row" :class="m.role">
            <div class="ad-bubble" :class="m.role">
              <!-- 工具调用：图标 + 状态（进行中 spinner / 完成 ✓ / 失败 ✕） -->
              <div v-if="m.role === 'assistant' && m.tools?.length" class="ad-tools">
                <span v-for="(t, k) in m.tools" :key="k" class="ad-tool" :class="t.status">
                  <span class="ad-tool-icon">{{ TOOL_ICON[t.name] || '🔧' }}</span>
                  <span class="ad-tool-text">{{ t.status === 'done' ? (TOOL_DONE[t.name] || t.label) : t.status === 'failed' ? t.label + '失败' : t.label }}</span>
                  <i v-if="t.status === 'running'" class="ad-spin" />
                  <span v-else-if="t.status === 'done'" class="ad-tool-ok">✓</span>
                  <span v-else class="ad-tool-fail">✕</span>
                </span>
              </div>
              <AssistantAnalysisCard v-for="(c, k) in (m.cards || [])" :key="'c' + k" :name="c.name" :data="c.data" />
              <div v-if="m.text && m.role === 'assistant'" class="ad-text md" v-html="renderMarkdown(m.text)"></div>
              <div v-else-if="m.text" class="ad-text">{{ m.text }}</div>
              <div v-else-if="m.streaming && !m.error" class="ad-typing"><i /><i /><i /></div>
              <div v-if="m.error" class="ad-err">
                <span>{{ m.error }}</span>
                <el-button link type="primary" size="small" @click="onRetry(i)">重试</el-button>
              </div>
              <!-- 复制 + 点赞点踩：只在助手已完成的回复上 -->
              <div v-if="m.role === 'assistant' && m.text && !m.streaming" class="ad-actions">
                <button class="ad-act" title="复制" @click="copyAnswer(m)">⧉ 复制</button>
                <button class="ad-act" :class="{ on: m.rating === 'up' }" :disabled="!!m.rating" title="有帮助" @click="rateAnswer(i, 'up')">👍</button>
                <button class="ad-act" :class="{ on: m.rating === 'down' }" :disabled="!!m.rating" title="没帮助" @click="rateAnswer(i, 'down')">👎</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="ad-composer">
          <div class="ad-input-row">
            <el-input
              v-model="input" :placeholder="activeTaskId ? '问问这份报告…' : '想问点什么？'"
              :disabled="streaming" @keyup.enter="onSend"
            />
            <el-button v-if="streaming" @click="onStop">停止</el-button>
            <el-button v-else type="primary" :disabled="!canSend" @click="onSend">发送</el-button>
          </div>
          <div class="ad-disclaimer">AI 生成内容仅供参考，不替代导师意见；助手不代写、不改写原文。</div>
        </div>
      </template>

      <!-- 历史会话列表 -->
      <div v-else class="ad-list">
        <div class="ad-history-head">
          <el-button link size="small" @click="showHistory = false">← 返回</el-button>
          <span class="ad-history-title">历史对话 · 保留 7 天</span>
        </div>
        <div v-if="loadingHistory" class="ad-history-empty">加载中…</div>
        <div v-else-if="historyList.length === 0" class="ad-history-empty">暂无历史对话</div>
        <div v-for="c in historyList" :key="c.conversationId" class="ad-history-item" @click="resumeConversation(c)">
          <div class="ad-history-item-main">
            <div class="ad-history-item-title">{{ c.title || '（无标题）' }}</div>
            <div class="ad-history-item-meta">{{ formatTime(c.updatedAt) }} · {{ c.turns }} 轮<span v-if="c.taskId"> · 报告 #{{ c.taskId }}</span></div>
          </div>
          <el-button link size="small" @click.stop="removeConversation(c)">删除</el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped lang="scss">
.ad { height: 100%; display: flex; flex-direction: column; }

/* ① 头部 */
.ad-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px; border-bottom: 1px solid var(--el-border-color-lighter);
}
.ad-title { display: flex; align-items: center; gap: 10px; }
.ad-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex: none;
  object-fit: cover;
  &.sm { width: 26px; height: 26px; }
}
.ad-name { font-weight: 600; font-size: 15px; }
.ad-head-actions { display: flex; gap: 2px; }
.ad-icon-btn { font-size: 15px; width: 32px; height: 32px; padding: 0; color: var(--el-text-color-regular); }

/* ② 报告选择 */
.ad-select-row { padding: 10px 16px 0; }
.ad-task-select { width: 100%; }
.ad-opt-title { float: left; max-width: 320px; overflow: hidden; text-overflow: ellipsis; }
.ad-opt-rate { float: right; color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; &.over { color: var(--el-color-danger); } }

/* ③ 上下文卡 */
.ad-ctx {
  margin: 10px 16px 0; padding: 10px 12px; border-radius: 12px;
  background: var(--el-color-primary-light-9); border: 1px solid var(--el-color-primary-light-8);
}
.ad-ctx-head { display: flex; align-items: center; gap: 6px; }
.ad-ctx-icon { flex: none; }
.ad-ctx-title { flex: 1; min-width: 0; font-size: 13px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ad-ctx-badge {
  flex: none; font-size: 11px; padding: 1px 8px; border-radius: 999px; font-weight: 600;
  &.ok { background: var(--el-color-success-light-9); color: var(--el-color-success-dark-2); }
  &.warn { background: var(--el-color-warning-light-9); color: var(--el-color-warning-dark-2); }
  &.bad { background: var(--el-color-danger-light-9); color: var(--el-color-danger-dark-2); }
}
.ad-ctx-meta { margin-top: 4px; font-size: 12px; color: var(--el-text-color-secondary); b { color: var(--el-text-color-primary); } .sep { margin: 0 6px; } }
.ad-ctx-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }

.ad-chip {
  cursor: pointer; font-size: 12px; padding: 3px 10px; border-radius: 999px;
  background: #fff; color: var(--el-text-color-primary); border: 1px solid var(--el-border-color-lighter);
  transition: background .15s;
  &:hover { background: var(--el-fill-color); }
  &.primary { background: var(--el-color-primary); color: #fff; border-color: var(--el-color-primary); &:hover { opacity: .9; } }
  &.red { color: var(--el-color-danger-dark-2); border-color: var(--el-color-danger-light-7); }
  &.yellow { color: var(--el-color-warning-dark-2); border-color: var(--el-color-warning-light-7); }
}

/* ④ 消息流 */
.ad-list { flex: 1; overflow-y: auto; padding: 14px 16px; background: var(--el-fill-color-lighter); margin-top: 10px; }
.ad-welcome { display: flex; align-items: flex-start; gap: 8px; margin-bottom: 12px; }
.ad-welcome-text {
  flex: 1; background: #fff; border-radius: 14px; border-top-left-radius: 4px;
  padding: 10px 14px; font-size: 14px; line-height: 1.55; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}
.ad-quick { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 14px 34px; }

.ad-row { display: flex; margin-bottom: 10px; &.user { justify-content: flex-end; } }
.ad-bubble {
  max-width: 88%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.55; position: relative;
  &.user { background: var(--el-color-primary); color: #fff; border-bottom-right-radius: 4px; }
  &.assistant { background: #fff; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
}
.ad-text { white-space: pre-wrap; word-break: break-word; }
.ad-text.md { white-space: normal; }
.ad-text.md :deep(p) { margin: 0 0 6px; line-height: 1.6; }
.ad-text.md :deep(p:last-child) { margin-bottom: 0; }
.ad-text.md :deep(h4), .ad-text.md :deep(h5), .ad-text.md :deep(h6) { margin: 8px 0 4px; font-size: 14px; font-weight: 600; }
.ad-text.md :deep(ul), .ad-text.md :deep(ol) { margin: 2px 0 6px; padding-left: 18px; }
.ad-text.md :deep(li) { margin: 2px 0; line-height: 1.55; }
.ad-text.md :deep(code) { font-size: 12px; padding: 1px 5px; border-radius: 4px; background: var(--el-fill-color); }
.ad-text.md :deep(pre) { margin: 6px 0; padding: 8px 10px; border-radius: 8px; background: var(--el-fill-color); overflow-x: auto; }
.ad-text.md :deep(pre code) { padding: 0; background: none; }
.ad-text.md :deep(blockquote) { margin: 6px 0; padding: 4px 10px; border-left: 3px solid var(--el-border-color); color: var(--el-text-color-secondary); }
.ad-text.md :deep(strong) { font-weight: 600; }

.ad-tools { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.ad-tool {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: var(--el-fill-color); color: var(--el-text-color-secondary);
  &.running { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
  &.done { color: var(--el-color-success-dark-2); background: var(--el-color-success-light-9); }
  &.failed { color: var(--el-color-danger); background: var(--el-color-danger-light-9); }
}
.ad-spin { width: 10px; height: 10px; border-radius: 50%; border: 2px solid currentColor; border-right-color: transparent; animation: adspin .8s linear infinite; }
@keyframes adspin { to { transform: rotate(360deg); } }
.ad-tool-ok, .ad-tool-fail { font-weight: 700; }

.ad-typing {
  display: flex; gap: 4px; padding: 4px 0;
  i { width: 6px; height: 6px; border-radius: 50%; background: #c0c4cc; animation: adblink 1.2s infinite; }
  i:nth-child(2) { animation-delay: 0.2s; }
  i:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes adblink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
.ad-err { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--el-color-danger); margin-top: 4px; }

.ad-actions { display: flex; justify-content: flex-end; gap: 2px; margin-top: 6px; opacity: .55; transition: opacity .15s; }
.ad-bubble:hover .ad-actions { opacity: 1; }
.ad-act {
  border: none; background: transparent; cursor: pointer; font-size: 12px; padding: 2px 6px; border-radius: 6px; color: var(--el-text-color-secondary);
  &:hover { background: var(--el-fill-color); }
  &.on { color: var(--el-color-primary); }
  &:disabled { cursor: default; }
}

/* 历史 */
.ad-history-head { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.ad-history-title { font-size: 13px; color: var(--el-text-color-secondary); }
.ad-history-empty { text-align: center; color: var(--el-text-color-placeholder); padding: 40px 0; font-size: 13px; }
.ad-history-item {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  background: #fff; border-radius: 10px; padding: 12px 14px; margin-bottom: 8px; cursor: pointer;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  &:hover { background: var(--el-fill-color); }
}
.ad-history-item-main { flex: 1; min-width: 0; }
.ad-history-item-title { font-size: 14px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ad-history-item-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }

/* 输入区 */
.ad-composer { border-top: 1px solid var(--el-border-color-lighter); padding: 10px 16px 10px; }
.ad-input-row { display: flex; gap: 8px; }
.ad-disclaimer { font-size: 11px; color: var(--el-text-color-placeholder); text-align: center; margin-top: 8px; }
</style>
