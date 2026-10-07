<script setup>
import { ref, computed, nextTick } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { chatStream, getQuickPrompts, listConversations, getConversation, deleteConversation } from '@/api/assistant'
import { listTasks, getTaskDetail } from '@/api/detect'
import { submitFeedback } from '@/api/feedback'
import { useAuth } from '@/store/auth'
import AssistantAnalysisCard from '@/components/AssistantAnalysisCard.vue'
import { renderMarkdown } from '@/utils/markdown'

/*
 * 论文检测助手 · 对话页
 * 布局按 docs/design/202610-assistant-chat-ui-redesign.md §2.2 分四区：
 *   导航（身份 + 历史/新对话）→ 报告选择（picker 一行）→ 上下文卡（绑定报告时）→ 消息流 + 输入
 * 入口：task/detail「问助手」（带 taskId / paragraphIdx）· 四个 tab 页 FAB（不带任务）
 * 协议：SSE meta / token / tool_call / tool_result / done / error，见 api/assistant.js
 */

const auth = useAuth()

/* 工具调用图标与完成态短标签（方案 §3.2） */
const TOOL_ICON = {
  get_task_detail: '📊', list_my_tasks: '🗂', explain_paragraph: '🔍', detect_text: '🧪',
  get_threshold_policy: '📏', search_knowledge: '📚', create_appeal: '✍️',
}
const TOOL_DONE = {
  get_task_detail: '已读取报告', list_my_tasks: '已查看记录', explain_paragraph: '已分析段落', detect_text: '已检测',
  get_threshold_policy: '已查阈值', search_knowledge: '已查资料', create_appeal: '已提交申诉',
}

const taskId = ref(null)             // null = 通用咨询
const paragraphIdx = ref(null)
const conversationId = ref('')
const messages = ref([])             // { role, text, tools:[], cards:[], error, streaming, rating }
const input = ref('')
const streaming = ref(false)
const welcome = ref('')
const prompts = ref([])
const scrollInto = ref('')
const statusBarHeight = ref(20)

// 报告上下文
const tasks = ref([])
const taskDetail = ref(null)

let stream = null

// ---- 本地持久化：切换页面/杀进程重进不丢（后端 MySQL 仍作 7 天跨设备备份）----
const LS_KEY = 'paperaigc_chat_state'

function persist() {
  try {
    uni.setStorageSync(LS_KEY, JSON.stringify({ conversationId: conversationId.value, taskId: taskId.value, messages: messages.value }))
  } catch (e) { /* 存储异常忽略 */ }
}

function restore() {
  try {
    const raw = uni.getStorageSync(LS_KEY)
    if (!raw) return
    const state = JSON.parse(raw)
    conversationId.value = state.conversationId || ''
    taskId.value = state.taskId ?? null
    messages.value = state.messages || []
  } catch (e) { /* 解析失败忽略 */ }
}

// ---- 历史会话 ----
const showHistory = ref(false)
const historyList = ref([])
const loadingHistory = ref(false)

const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
const showQuick = computed(() => messages.value.length === 0 && prompts.value.length > 0)
const activeTask = computed(() => tasks.value.find((t) => t.id === taskId.value) || null)
const riskParagraphs = computed(() => {
  const ps = taskDetail.value?.paragraphs || []
  return ps
    .filter((p) => !p.excluded && (p.calibratedProb ?? 0) >= 0.4)
    .sort((a, b) => (b.calibratedProb ?? 0) - (a.calibratedProb ?? 0))
    .slice(0, 6)
})
const bodyCount = computed(() => (taskDetail.value?.paragraphs || []).filter((p) => !p.excluded).length)

/* 报告选择 picker：第 0 项是通用咨询 */
const pickerLabels = computed(() => ['通用咨询', ...tasks.value.map((t) => `${t.paperTitle} · AI ${t.aiRate == null ? '—' : t.aiRate.toFixed(0) + '%'}`)])
const pickerIndex = computed(() => {
  const i = tasks.value.findIndex((t) => t.id === taskId.value)
  return i < 0 ? 0 : i + 1
})
function onPickTask(e) {
  const i = Number(e.detail.value)
  selectTask(i <= 0 ? undefined : tasks.value[i - 1]?.id)
}

/* 上下文卡达标徽章：沿用报告页颜色逻辑 */
const taskBadge = computed(() => {
  const t = activeTask.value
  if (!t || t.aiRate == null) return null
  const diff = t.aiRate - t.threshold
  if (diff <= 0) return { text: '✓ 达标', cls: 'ok' }
  return { text: `超标 ${diff.toFixed(1)}pp`, cls: diff <= t.threshold * 0.5 ? 'warn' : 'bad' }
})

onLoad(async (query) => {
  const sys = uni.getSystemInfoSync()
  statusBarHeight.value = sys.statusBarHeight || 20
  restore()
  const restored = messages.value.length > 0
  loadTasks()
  if (!restored) {
    if (query?.taskId) taskId.value = Number(query.taskId)
    if (query?.paragraphIdx !== undefined && query.paragraphIdx !== '') paragraphIdx.value = Number(query.paragraphIdx)
    if (query?.conversationId) conversationId.value = query.conversationId
  }
  await refreshPrompts(taskId.value || undefined)
  if (taskId.value != null && taskDetail.value == null) {
    try { taskDetail.value = await getTaskDetail(taskId.value) } catch (e) { taskDetail.value = null }
  }
  if (!restored && taskId.value != null && paragraphIdx.value != null) {
    send(`第 ${paragraphIdx.value + 1} 段为什么会被判成像 AI？`)
  }
})

onUnload(() => {
  stream?.abort()
  persist()
})

function loadTasks() {
  listTasks()
    .then((rows) => { tasks.value = (rows || []).filter((t) => t.status === 'DONE') })
    .catch(() => { tasks.value = [] })
}

async function refreshPrompts(id) {
  try {
    const qp = await getQuickPrompts(id)
    welcome.value = qp?.welcome || ''
    prompts.value = qp?.prompts || []
  } catch (e) {
    welcome.value = '嗨，我是论文检测助手。检测结果看不懂、不知道怎么改，都可以直接问我。'
  }
}

async function selectTask(id) {
  if (streaming.value) stream?.abort()
  taskId.value = id ?? null
  conversationId.value = ''
  messages.value = []
  taskDetail.value = null
  paragraphIdx.value = null
  persist()
  await refreshPrompts(id)
  if (id != null) {
    try { taskDetail.value = await getTaskDetail(id) } catch (e) { taskDetail.value = null }
  }
}

function analyzeParagraph(idx) {
  paragraphIdx.value = idx
  send(`第 ${idx + 1} 段为什么会被判成像 AI？`)
}

function analyzeOverall() {
  const d = taskDetail.value
  if (!d) return
  const rate = d.aiRate != null ? `${d.aiRate.toFixed(1)}%` : '未知'
  send(`这份报告整体 AI 率是 ${rate}（红线 ${d.threshold}%）。帮我分析一下可能的原因，以及哪几段最该先改。`)
}

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/home/home' })
}

function scrollBottom() {
  nextTick(() => {
    scrollInto.value = ''
    nextTick(() => { scrollInto.value = 'msg-bottom' })
  })
}

function onQuick(q) { send(q) }

function onSend() {
  if (!canSend.value) return
  const text = input.value.trim()
  input.value = ''
  send(text)
}

function send(text) {
  if (streaming.value) return
  messages.value.push({ role: 'user', text })
  const reply = { role: 'assistant', text: '', tools: [], cards: [], error: null, streaming: true }
  messages.value.push(reply)
  streaming.value = true
  scrollBottom()

  const payload = {
    message: text,
    conversationId: conversationId.value || undefined,
    taskId: taskId.value || undefined,
    paragraphIdx: paragraphIdx.value ?? undefined,
    userId: auth.userId ? Number(auth.userId) : undefined,
    clientContext: { platform: 'uniapp', page: 'assistant/chat' },
  }
  paragraphIdx.value = null

  stream = chatStream(payload, {
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
          reply.tools.push({ name: data?.name, label: data?.label || data?.name, status: 'running' })
          break
        case 'tool_result': {
          const t = reply.tools.find((x) => x.name === data?.name && x.status === 'running')
          if (t) t.status = data?.ok === false ? 'failed' : 'done'
          if (data?.card) reply.cards.push({ name: data.name, data: data.card })
          break
        }
        case 'error':
          reply.error = data?.message || '助手出了点问题，稍后再试'
          reply.errorCode = data?.code
          break
        default:
          break
      }
    },
    onError: (err) => { reply.error = err?.message || '网络异常' },
  })

  stream.done.finally(() => {
    reply.streaming = false
    streaming.value = false
    if (!reply.text && !reply.error) reply.error = '助手没有返回内容，再试一次'
    persist()
    scrollBottom()
  })
}

function onStop() { stream?.abort() }

function onRetry(idx) {
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
  if (streaming.value) stream?.abort()
  conversationId.value = ''
  messages.value = []
  streaming.value = false
  persist()
}

// ---- 复制 + 点赞点踩（方案 §3.4）----
function copyAnswer(m) {
  uni.setClipboardData({ data: m.text, showToast: false, success: () => uni.showToast({ title: '已复制', icon: 'none' }) })
}

async function rateAnswer(idx, rating) {
  const m = messages.value[idx]
  if (!m || m.rating) return
  const q = [...messages.value.slice(0, idx)].reverse().find((x) => x.role === 'user')?.text || ''
  m.rating = rating
  persist()
  try {
    await submitFeedback({
      category: 'suggestion',
      content: `[助手${rating === 'up' ? '点赞' : '点踩'}] 会话 ${conversationId.value || '-'}\n问：${q.slice(0, 300)}\n答：${m.text.slice(0, 600)}`,
      taskId: taskId.value || undefined,
      userId: auth.userId ? Number(auth.userId) : undefined,
    })
    uni.showToast({ title: rating === 'up' ? '谢谢，已记录' : '已记录，我们会改进', icon: 'none' })
  } catch (e) { /* 未登录等情况保留本地标记 */ }
}

// ---- 历史会话 ----
async function openHistory() {
  showHistory.value = true
  await loadHistory()
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    historyList.value = await listConversations(auth.userId ? Number(auth.userId) : undefined, 30)
  } catch (e) {
    historyList.value = []
  } finally {
    loadingHistory.value = false
  }
}

async function resumeConversation(c) {
  try {
    const detail = await getConversation(c.conversationId)
    conversationId.value = c.conversationId
    if (c.taskId != null && c.taskId !== taskId.value) {
      taskId.value = c.taskId
      taskDetail.value = null
      try { taskDetail.value = await getTaskDetail(c.taskId) } catch (e) { taskDetail.value = null }
      await refreshPrompts(c.taskId)
    }
    messages.value = (detail.messages || [])
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, text: m.content, tools: [], cards: [], error: null, streaming: false }))
    showHistory.value = false
    persist()
    scrollBottom()
  } catch (e) { /* toast 由请求层 */ }
}

async function removeConversation(c) {
  try {
    await deleteConversation(c.conversationId)
    historyList.value = historyList.value.filter((x) => x.conversationId !== c.conversationId)
    if (conversationId.value === c.conversationId) {
      conversationId.value = ''
      messages.value = []
      persist()
    }
  } catch (e) { /* ignore */ }
}

function formatTime(t) {
  const ts = typeof t === 'number' ? t * 1000 : Date.parse(t)
  if (!ts || isNaN(ts)) return ''
  const diff = Date.now() - ts
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${Math.floor(diff / 86400000)} 天前`
}

const pct = (p) => `${((p ?? 0) * 100).toFixed(0)}%`
</script>

<template>
  <view class="page">
    <!-- ① 导航：身份 + 全局操作 -->
    <view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="nav-inner">
        <text class="nav-btn" @click="goBack">‹</text>
        <view class="nav-center">
          <view class="nav-avatar">AI</view>
          <text class="nav-title">论文检测助手</text>
        </view>
        <view class="nav-right">
          <text class="nav-icon" @click="openHistory">🕘</text>
          <text class="nav-icon" @click="onNewChat">✚</text>
        </view>
      </view>
    </view>

    <!-- 历史会话列表 -->
    <view v-if="showHistory" class="history">
      <view class="history-head">
        <text class="history-back" @click="showHistory = false">← 返回</text>
        <text class="history-title">历史对话 · 保留 7 天</text>
      </view>
      <scroll-view class="history-list" scroll-y>
        <view v-if="loadingHistory" class="history-empty">加载中…</view>
        <view v-else-if="historyList.length === 0" class="history-empty">暂无历史对话</view>
        <view v-for="c in historyList" :key="c.conversationId" class="history-item" @click="resumeConversation(c)">
          <view class="history-item-main">
            <text class="history-item-title">{{ c.title || '（无标题）' }}</text>
            <text class="history-item-meta">{{ formatTime(c.updatedAt) }} · {{ c.turns }} 轮<template v-if="c.taskId"> · 报告 #{{ c.taskId }}</template></text>
          </view>
          <text class="history-del" @click.stop="removeConversation(c)">删除</text>
        </view>
      </scroll-view>
    </view>

    <template v-else>
      <!-- ② 报告选择：一行 picker -->
      <view v-if="tasks.length" class="select-row">
        <picker mode="selector" :range="pickerLabels" :value="pickerIndex" @change="onPickTask">
          <view class="select-box">
            <text class="select-icon">📄</text>
            <text class="select-text">{{ pickerLabels[pickerIndex] }}</text>
            <text class="select-chevron">⌄</text>
          </view>
        </picker>
      </view>

      <!-- ③ 上下文卡：绑定报告时 -->
      <view v-if="activeTask" class="ctx">
        <view class="ctx-head">
          <text class="ctx-title">《{{ activeTask.paperTitle }}》</text>
          <text v-if="taskBadge" class="ctx-badge" :class="taskBadge.cls">{{ taskBadge.text }}</text>
        </view>
        <text class="ctx-meta">整体 AI {{ activeTask.aiRate == null ? '—' : activeTask.aiRate.toFixed(1) + '%' }} · 红线 {{ activeTask.threshold }}%<template v-if="taskDetail"> · 正文 {{ bodyCount }} 段</template></text>
        <scroll-view v-if="taskDetail" class="ctx-chips" scroll-x :show-scrollbar="false">
          <view class="ctx-chips-inner">
            <view class="chip primary" hover-class="chip--hover" @click="analyzeOverall"><text>整体怎么看</text></view>
            <view
              v-for="p in riskParagraphs" :key="p.paragraphIdx"
              class="chip" :class="(p.calibratedProb ?? 0) >= 0.7 ? 'red' : 'yellow'"
              hover-class="chip--hover" @click="analyzeParagraph(p.paragraphIdx)"
            ><text>段 {{ p.paragraphIdx + 1 }} · {{ pct(p.calibratedProb) }}</text></view>
          </view>
        </scroll-view>
      </view>

      <!-- ④ 消息流 -->
      <scroll-view class="msgs" scroll-y :scroll-into-view="scrollInto" scroll-with-animation>
        <view class="msgs-inner">
          <view class="welcome">
            <view class="welcome-avatar">AI</view>
            <text class="welcome-text">{{ welcome }}</text>
          </view>

          <view v-if="showQuick" class="quick">
            <view v-for="q in prompts" :key="q" class="chip" hover-class="chip--hover" @click="onQuick(q)"><text>{{ q }}</text></view>
          </view>

          <view v-for="(m, i) in messages" :key="i" class="row" :class="m.role">
            <view class="bubble" :class="m.role">
              <!-- 工具调用：图标 + 状态 -->
              <view v-if="m.role === 'assistant' && m.tools?.length" class="tools">
                <view v-for="(t, k) in m.tools" :key="k" class="tool" :class="t.status">
                  <text class="tool-icon">{{ TOOL_ICON[t.name] || '🔧' }}</text>
                  <text class="tool-text">{{ t.status === 'done' ? (TOOL_DONE[t.name] || t.label) : t.status === 'failed' ? t.label + '失败' : t.label }}</text>
                  <view v-if="t.status === 'running'" class="spin" />
                  <text v-else class="tool-mark">{{ t.status === 'done' ? '✓' : '✕' }}</text>
                </view>
              </view>
              <AssistantAnalysisCard v-for="(c, k) in (m.cards || [])" :key="'c' + k" :name="c.name" :data="c.data" />
              <rich-text v-if="m.text && m.role === 'assistant'" class="bubble-md" :nodes="renderMarkdown(m.text)" user-select />
              <text v-else-if="m.text" class="bubble-text" user-select>{{ m.text }}</text>
              <view v-else-if="m.streaming && !m.error" class="typing">
                <view class="dot" /><view class="dot" /><view class="dot" />
              </view>
              <view v-if="m.error" class="err">
                <text class="err-text">{{ m.error }}</text>
                <text class="err-retry" @click="onRetry(i)">重试</text>
              </view>
              <!-- 复制 + 点赞点踩 -->
              <view v-if="m.role === 'assistant' && m.text && !m.streaming" class="actions">
                <text class="act" @click="copyAnswer(m)">⧉ 复制</text>
                <text class="act" :class="{ on: m.rating === 'up', off: m.rating && m.rating !== 'up' }" @click="rateAnswer(i, 'up')">👍</text>
                <text class="act" :class="{ on: m.rating === 'down', off: m.rating && m.rating !== 'down' }" @click="rateAnswer(i, 'down')">👎</text>
              </view>
            </view>
          </view>
          <view id="msg-bottom" class="bottom-anchor" />
        </view>
      </scroll-view>

      <!-- 输入区 -->
      <view class="composer">
        <view class="composer-row">
          <input
            v-model="input" class="composer-input"
            :placeholder="taskId ? '问问这份报告…' : '想问点什么？'"
            confirm-type="send" :disabled="streaming" @confirm="onSend"
          />
          <button v-if="streaming" class="send-btn stop" @click="onStop">停止</button>
          <button v-else class="send-btn" :disabled="!canSend" @click="onSend">发送</button>
        </view>
        <text class="disclaimer">AI 生成内容仅供参考，不替代导师意见；助手不代写、不改写原文。</text>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page { height: 100vh; display: flex; flex-direction: column; background: $bg-grouped-primary; }

/* ① 导航 */
.nav { background: $bg-primary; border-bottom: $stroke-hairline solid $separator; }
.nav-inner { height: 88rpx; padding: 0 $sp-4; display: flex; align-items: center; justify-content: space-between; }
.nav-btn { color: $brand-primary; font-size: $fs-title-2; width: 60rpx; }
.nav-center { display: flex; align-items: center; gap: $sp-2; }
.nav-avatar {
  width: 52rpx; height: 52rpx; border-radius: $radius-pill;
  background: $brand-gradient-vivid; color: #fff; font-size: $fs-caption-2; font-weight: $fw-bold;
  display: flex; align-items: center; justify-content: center;
}
.nav-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.nav-right { display: flex; align-items: center; gap: $sp-3; }
.nav-icon { font-size: $fs-title-3; color: $label-secondary; padding: 0 $sp-1; }

/* 历史 */
.history { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.history-head { display: flex; align-items: center; gap: $sp-3; padding: $sp-3 $sp-4; background: $bg-primary; border-bottom: $stroke-hairline solid $separator; }
.history-back { color: $brand-primary; font-size: $fs-body; }
.history-title { font-size: $fs-footnote; color: $label-secondary; }
.history-list { flex: 1; min-height: 0; padding: $sp-3 $sp-4; }
.history-empty { text-align: center; color: $label-tertiary; font-size: $fs-footnote; padding: 80rpx 0; }
.history-item { display: flex; align-items: center; justify-content: space-between; gap: $sp-3; background: $bg-primary; border-radius: $radius-card; padding: $sp-3 $sp-4; margin-bottom: $sp-2; box-shadow: $shadow-card; }
.history-item-main { flex: 1; min-width: 0; }
.history-item-title { font-size: $fs-subhead; font-weight: $fw-medium; color: $label-primary; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-item-meta { font-size: $fs-caption-2; color: $label-secondary; margin-top: 4rpx; }
.history-del { flex: none; font-size: $fs-footnote; color: $danger-fg; }

/* ② 报告选择 */
.select-row { flex: none; padding: $sp-2 $sp-4 0; background: $bg-grouped-primary; }
.select-box {
  display: flex; align-items: center; gap: $sp-2;
  height: 72rpx; padding: 0 $sp-3;
  border-radius: $radius-md; background: $bg-primary; border: $stroke-hairline solid $separator;
}
.select-icon { flex: none; font-size: $fs-footnote; }
.select-text { flex: 1; font-size: $fs-footnote; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.select-chevron { flex: none; color: $label-tertiary; font-size: $fs-subhead; }

/* ③ 上下文卡 */
.ctx {
  flex: none; margin: $sp-2 $sp-4 0; padding: $sp-3;
  border-radius: $radius-md; background: $brand-primary-wash; border: $stroke-hairline solid rgba(0, 122, 255, 0.18);
}
.ctx-head { display: flex; align-items: center; gap: $sp-2; }
.ctx-title { flex: 1; min-width: 0; font-size: $fs-footnote; font-weight: $fw-semibold; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.ctx-badge {
  flex: none; font-size: $fs-caption-2; font-weight: $fw-semibold; padding: 2rpx $sp-2; border-radius: $radius-pill;
  &.ok { background: $success-bg; color: $success-fg; } &.warn { background: $warning-bg; color: $warning-fg; } &.bad { background: $danger-bg; color: $danger-fg; }
}
.ctx-meta { display: block; margin-top: 4rpx; font-size: $fs-caption-1; color: $label-secondary; }
.ctx-chips { margin-top: $sp-2; white-space: nowrap; }
.ctx-chips-inner { display: inline-flex; gap: $sp-2; }

.chip {
  display: inline-flex; align-items: center; flex: none;
  padding: $sp-1 $sp-3; border-radius: $radius-pill;
  background: $bg-primary; color: $label-primary; border: $stroke-hairline solid $separator;
  font-size: $fs-footnote;
  &--hover { opacity: 0.6; }
  &.primary { background: $brand-primary; color: #fff; border-color: $brand-primary; font-weight: $fw-medium; }
  &.red { color: $danger-fg; border-color: rgba(255, 59, 48, 0.35); }
  &.yellow { color: $warning-fg; border-color: rgba(255, 149, 0, 0.35); }
}

/* ④ 消息流 */
.msgs { flex: 1; min-height: 0; }
.msgs-inner { padding: $sp-3 $sp-4 $sp-2; }
.bottom-anchor { height: 2rpx; }

.welcome { display: flex; align-items: flex-start; gap: $sp-2; margin-bottom: $sp-3; }
.welcome-avatar {
  flex: none; width: 56rpx; height: 56rpx; border-radius: $radius-pill;
  background: $brand-gradient-vivid; color: #fff; font-size: $fs-caption-2; font-weight: $fw-bold;
  display: flex; align-items: center; justify-content: center;
}
.welcome-text {
  flex: 1; background: $bg-primary; padding: $sp-3 $sp-4;
  border-radius: $radius-card; border-top-left-radius: $radius-xs;
  font-size: $fs-subhead; line-height: $lh-normal; color: $label-primary; box-shadow: $shadow-card;
}
.quick { display: flex; flex-wrap: wrap; gap: $sp-2; margin: 0 0 $sp-4 (56rpx + $sp-2); }

.row { display: flex; margin-bottom: $sp-3; &.user { justify-content: flex-end; } &.assistant { justify-content: flex-start; } }
.bubble {
  max-width: 86%; padding: $sp-3 $sp-4; border-radius: $radius-card;
  font-size: $fs-subhead; line-height: $lh-normal;
  &.user { background: $brand-primary; color: #fff; border-bottom-right-radius: $radius-xs; }
  &.assistant { background: $bg-primary; color: $label-primary; border-bottom-left-radius: $radius-xs; box-shadow: $shadow-card; }
}
.bubble-text { white-space: pre-wrap; word-break: break-word; }
.bubble-md { display: block; word-break: break-word; line-height: $lh-normal; }
.bubble-md :deep(.md-p) { margin: 0 0 $sp-1; }
.bubble-md :deep(.md-h) { display: block; margin: $sp-2 0 4rpx; font-weight: $fw-semibold; }
.bubble-md :deep(.md-list) { margin: 4rpx 0 $sp-1; padding-left: 36rpx; }
.bubble-md :deep(.md-li) { margin: 2rpx 0; }
.bubble-md :deep(.md-code) { font-family: $font-family-mono; font-size: $fs-caption-1; padding: 0 6rpx; border-radius: $radius-xs; background: $fill-tertiary; }
.bubble-md :deep(.md-pre) { display: block; margin: $sp-1 0; padding: $sp-2 $sp-3; border-radius: $radius-sm; background: $fill-tertiary; font-family: $font-family-mono; font-size: $fs-caption-1; white-space: pre-wrap; }
.bubble-md :deep(.md-quote) { display: block; margin: $sp-1 0; padding: 4rpx $sp-3; border-left: 4rpx solid $separator-opaque; color: $label-secondary; }

.tools { display: flex; flex-wrap: wrap; gap: $sp-1; margin-bottom: $sp-2; }
.tool {
  display: inline-flex; align-items: center; gap: 6rpx;
  font-size: $fs-caption-2; padding: 2rpx $sp-2; border-radius: $radius-pill;
  background: $fill-quaternary; color: $label-secondary;
  &.running { color: $brand-primary; background: $brand-primary-wash; }
  &.done { color: $success-fg; background: $success-bg; }
  &.failed { color: $danger-fg; background: $danger-bg; }
}
.spin { width: 18rpx; height: 18rpx; border-radius: 50%; border: 3rpx solid currentColor; border-right-color: transparent; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.tool-mark { font-weight: $fw-bold; }

.typing { display: flex; gap: 8rpx; padding: 6rpx 0; }
.dot { width: 12rpx; height: 12rpx; border-radius: 50%; background: $label-tertiary; animation: blink 1.2s infinite ease-in-out; &:nth-child(2) { animation-delay: 0.2s; } &:nth-child(3) { animation-delay: 0.4s; } }
@keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }

.err { display: flex; align-items: center; gap: $sp-3; margin-top: $sp-1; }
.err-text { font-size: $fs-footnote; color: $danger-fg; }
.err-retry { font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-medium; }

.actions { display: flex; justify-content: flex-end; gap: $sp-3; margin-top: $sp-2; padding-top: $sp-1; border-top: $stroke-hairline solid $separator; }
.act { font-size: $fs-caption-1; color: $label-secondary; &.on { color: $brand-primary; } &.off { opacity: 0.35; } }

/* 输入区 */
.composer {
  background: $bg-primary; border-top: $stroke-hairline solid $separator;
  padding: $sp-2 $sp-4; padding-bottom: #{"calc(#{$sp-2} + env(safe-area-inset-bottom))"};
}
.composer-row { display: flex; align-items: center; gap: $sp-2; }
.composer-input { flex: 1; height: 76rpx; padding: 0 $sp-4; border-radius: $radius-pill; background: $fill-tertiary; font-size: $fs-subhead; color: $label-primary; }
.send-btn {
  flex: none; margin: 0; height: 76rpx; line-height: 76rpx; padding: 0 $sp-4; border-radius: $radius-pill;
  background: $brand-primary; color: #fff; font-size: $fs-subhead; font-weight: $fw-semibold;
  &::after { border: none; }
  &[disabled] { background: $fill-secondary; color: $label-tertiary; }
  &.stop { background: $fill-secondary; color: $label-primary; }
}
.disclaimer { display: block; font-size: $fs-caption-2; color: $label-tertiary; text-align: center; margin-top: $sp-2; }
</style>
