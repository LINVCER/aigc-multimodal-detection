<script setup>
import { ref, computed, nextTick } from 'vue'
import { onLoad, onUnload } from '@dcloudio/uni-app'
import { chatStream, getQuickPrompts, listConversations, getConversation, deleteConversation } from '@/api/assistant'
import { listTasks, getTaskDetail } from '@/api/detect'
import { useAuth } from '@/store/auth'
import AssistantAnalysisCard from '@/components/AssistantAnalysisCard.vue'

/*
 * 论文检测助手 · 对话页
 * 入口：task/detail「问助手」（带 taskId / paragraphIdx）· 四个 tab 页右下角 FAB（不带任务）
 * 协议：SSE meta / token / tool_call / tool_result / done / error，见 api/assistant.js
 *
 * 报告选择条：复用 listTasks 列出最近 DONE 报告，点选绑定对话上下文；
 * 绑定后复用 getTaskDetail 出「整体分析 + 高风险段落」快捷条，一键「分析原因」。
 */

const auth = useAuth()

const taskId = ref(null)             // null = 通用咨询
const paragraphIdx = ref(null)
const conversationId = ref('')
const messages = ref([])             // { role, text, tools:[], error, streaming }
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
    uni.setStorageSync(LS_KEY, JSON.stringify({
      conversationId: conversationId.value,
      taskId: taskId.value,
      messages: messages.value,
    }))
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

// ---- 历史会话（聊天记录，后端保留 7 天）----
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

onLoad(async (query) => {
  const sys = uni.getSystemInfoSync()
  statusBarHeight.value = sys.statusBarHeight || 20
  // 1) 每次进入页面都是新实例，先恢复本地暂存会话
  restore()
  const restored = messages.value.length > 0
  loadTasks()
  // 2) 无历史会话时才用 query 初始化；有历史则尊重恢复的上下文，不清空
  if (!restored) {
    if (query?.taskId) taskId.value = Number(query.taskId)
    if (query?.paragraphIdx !== undefined && query.paragraphIdx !== '') paragraphIdx.value = Number(query.paragraphIdx)
    if (query?.conversationId) conversationId.value = query.conversationId
  }
  await refreshPrompts(taskId.value || undefined)
  if (taskId.value != null && taskDetail.value == null) {
    try { taskDetail.value = await getTaskDetail(taskId.value) } catch (e) { taskDetail.value = null }
  }
  // 3) 「为什么这段像 AI」直达：仅无历史会话时（避免把新段落追问绑到旧会话）
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
  taskId.value = id
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
  // 段落直达只在首问带，后续按对话上下文走
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
        case 'done':
          break
        default:
          break
      }
    },
    onError: (err) => {
      reply.error = err?.message || '网络异常'
    },
  })

  stream.done.finally(() => {
    reply.streaming = false
    streaming.value = false
    if (!reply.text && !reply.error) reply.error = '助手没有返回内容，再试一次'
    persist()
    scrollBottom()
  })
}

function onStop() {
  stream?.abort()
}

function onRetry(idx) {
  // 找到上一条用户消息重发
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

// ---- 历史会话（聊天记录）----
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
      .map((m) => ({ role: m.role, text: m.content, tools: [], error: null, streaming: false }))
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
</script>

<template>
  <view class="page">
    <!-- 自定义导航 -->
    <view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="nav-inner">
        <text class="nav-btn" @click="goBack">‹ 返回</text>
        <view class="nav-center">
          <text class="nav-title">论文检测助手</text>
          <text v-if="activeTask" class="nav-sub">{{ activeTask.paperTitle }}</text>
        </view>
        <view class="nav-right">
          <text class="nav-btn" @click="openHistory">历史</text>
          <text class="nav-btn" @click="onNewChat">新对话</text>
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
            <text class="history-item-meta">{{ formatTime(c.updatedAt) }} · {{ c.turns }} 轮</text>
          </view>
          <text class="history-del" @click.stop="removeConversation(c)">删除</text>
        </view>
      </scroll-view>
    </view>

    <!-- 对话内容 -->
    <template v-else>
    <!-- 报告选择条 -->
    <scroll-view v-if="tasks.length" class="task-strip" scroll-x :show-scrollbar="false">
      <view class="task-strip-inner">
        <view class="task-chip" :class="{ active: taskId == null }" @click="selectTask(undefined)">
          <text class="task-chip-title">通用咨询</text>
        </view>
        <view
          v-for="t in tasks" :key="t.id"
          class="task-chip" :class="{ active: taskId === t.id }" @click="selectTask(t.id)"
        >
          <text class="task-chip-title">{{ t.paperTitle }}</text>
          <text v-if="t.aiRate != null" class="task-chip-rate">AI {{ t.aiRate.toFixed(0) }}%</text>
        </view>
      </view>
    </scroll-view>

    <!-- 段落分析条（绑定报告后，一键「分析原因」） -->
    <view v-if="taskId != null && riskParagraphs.length" class="para-strip">
      <view class="para-chip primary" hover-class="para-chip--hover" @click="analyzeOverall">
        <text>📊 整体怎么看</text>
      </view>
      <view
        v-for="p in riskParagraphs" :key="p.paragraphIdx"
        class="para-chip" hover-class="para-chip--hover" @click="analyzeParagraph(p.paragraphIdx)"
      >
        <text>段 {{ p.paragraphIdx + 1 }} · {{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%</text>
      </view>
    </view>

    <!-- 消息流 -->
    <scroll-view class="msgs" scroll-y :scroll-into-view="scrollInto" scroll-with-animation>
      <view class="msgs-inner">
        <!-- 欢迎卡 -->
        <view class="welcome">
          <view class="welcome-avatar">AI</view>
          <text class="welcome-text">{{ welcome }}</text>
        </view>

        <!-- 快捷问题 -->
        <view v-if="showQuick" class="quick">
          <view v-for="q in prompts" :key="q" class="quick-chip" hover-class="quick-chip--hover" @click="onQuick(q)">
            <text>{{ q }}</text>
          </view>
        </view>

        <!-- 对话气泡 -->
        <view v-for="(m, i) in messages" :key="i" class="row" :class="m.role">
          <view class="bubble" :class="m.role">
            <!-- 工具调用提示 -->
            <view v-if="m.role === 'assistant' && m.tools?.length" class="tools">
              <text v-for="(t, k) in m.tools" :key="k" class="tool-chip" :class="t.status">
                {{ t.status === 'running' ? '正在' : '' }}{{ t.label }}{{ t.status === 'failed' ? '（失败）' : '' }}
              </text>
            </view>
            <!-- 结构化分析卡：工具返回的数据直接渲染，正文是助手的「翻译」 -->
            <AssistantAnalysisCard v-for="(c, k) in (m.cards || [])" :key="'c' + k" :name="c.name" :data="c.data" />
            <text v-if="m.text" class="bubble-text" user-select>{{ m.text }}</text>
            <view v-else-if="m.streaming && !m.error" class="typing">
              <view class="dot" /><view class="dot" /><view class="dot" />
            </view>
            <view v-if="m.error" class="err">
              <text class="err-text">{{ m.error }}</text>
              <text class="err-retry" @click="onRetry(i)">重试</text>
            </view>
          </view>
        </view>
        <view id="msg-bottom" class="bottom-anchor" />
      </view>
    </scroll-view>

    <!-- 输入区 -->
    <view class="composer">
      <text class="disclaimer">AI 生成内容仅供参考，不替代导师意见；助手不代写、不改写原文。</text>
      <view class="composer-row">
        <input
          v-model="input"
          class="composer-input"
          :placeholder="taskId ? '问问这份报告…' : '想问点什么？'"
          confirm-type="send"
          :disabled="streaming"
          @confirm="onSend"
        />
        <button v-if="streaming" class="send-btn stop" @click="onStop">停止</button>
        <button v-else class="send-btn" :disabled="!canSend" @click="onSend">发送</button>
      </view>
    </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
.page {
  height: 100vh;
  display: flex; flex-direction: column;
  background: $bg-grouped-primary;
}

/* ===== 导航 ===== */
.nav {
  background: $bg-primary;
  border-bottom: $stroke-hairline solid $separator;
}
.nav-inner {
  height: 88rpx; padding: 0 $sp-4;
  display: flex; align-items: center; justify-content: space-between;
}
.nav-btn { color: $brand-primary; font-size: $fs-body; }
.nav-center { display: flex; flex-direction: column; align-items: center; max-width: 55%; }
.nav-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.nav-sub {
  font-size: $fs-caption-2; color: $label-secondary; margin-top: 2rpx;
  max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.nav-right { display: flex; align-items: center; gap: $sp-3; }

/* ===== 历史会话 ===== */
.history { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.history-head {
  display: flex; align-items: center; gap: $sp-3;
  padding: $sp-3 $sp-4;
  background: $bg-primary;
  border-bottom: $stroke-hairline solid $separator;
}
.history-back { color: $brand-primary; font-size: $fs-body; }
.history-title { font-size: $fs-footnote; color: $label-secondary; }
.history-list { flex: 1; min-height: 0; padding: $sp-3 $sp-4; }
.history-empty { text-align: center; color: $label-tertiary; font-size: $fs-footnote; padding: 80rpx 0; }
.history-item {
  display: flex; align-items: center; justify-content: space-between; gap: $sp-3;
  background: $bg-primary; border-radius: $radius-card; padding: $sp-3 $sp-4;
  margin-bottom: $sp-2; box-shadow: $shadow-card;
}
.history-item-main { flex: 1; min-width: 0; }
.history-item-title {
  font-size: $fs-subhead; font-weight: $fw-medium; color: $label-primary;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.history-item-meta { font-size: $fs-caption-2; color: $label-secondary; margin-top: 4rpx; }
.history-del { flex: none; font-size: $fs-footnote; color: $danger-fg; }

/* ===== 报告选择条 ===== */
.task-strip {
  flex: none;
  background: $bg-primary;
  border-bottom: $stroke-hairline solid $separator;
  white-space: nowrap;
}
.task-strip-inner { display: inline-flex; gap: $sp-2; padding: $sp-2 $sp-4; }
.task-chip {
  display: inline-flex; flex-direction: column; gap: 2rpx;
  max-width: 320rpx;
  padding: $sp-1 $sp-3;
  border-radius: $radius-pill;
  background: $fill-tertiary;
  border: $stroke-hairline solid transparent;
  &.active { background: $brand-primary-wash; border-color: $brand-primary; }
}
.task-chip-title {
  font-size: $fs-footnote; color: $label-primary; font-weight: $fw-medium;
  max-width: 300rpx; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.task-chip-rate { font-size: $fs-caption-2; color: $label-secondary; }
.task-chip.active .task-chip-title { color: $brand-primary; }

/* ===== 段落分析条 ===== */
.para-strip {
  flex: none;
  display: flex; gap: $sp-2; overflow-x: auto;
  padding: $sp-2 $sp-4;
  background: $brand-primary-wash;
  white-space: nowrap;
  &::-webkit-scrollbar { display: none; }
}
.para-chip {
  flex: none;
  padding: $sp-1 $sp-3;
  border-radius: $radius-pill;
  background: $bg-primary; color: $label-primary;
  font-size: $fs-footnote;
  &--hover { opacity: 0.6; }
  &.primary { background: $brand-primary; color: #fff; font-weight: $fw-medium; }
}

/* ===== 消息流 ===== */
.msgs { flex: 1; min-height: 0; }
.msgs-inner { padding: $sp-4 $sp-4 $sp-2; }
.bottom-anchor { height: 2rpx; }

.welcome {
  display: flex; align-items: flex-start; gap: $sp-3;
  margin-bottom: $sp-4;
}
.welcome-avatar {
  flex: none;
  width: 72rpx; height: 72rpx; border-radius: $radius-pill;
  background: $brand-gradient-vivid; color: #fff;
  font-size: $fs-footnote; font-weight: $fw-bold;
  display: flex; align-items: center; justify-content: center;
}
.welcome-text {
  flex: 1;
  background: $bg-primary;
  padding: $sp-3 $sp-4;
  border-radius: $radius-card;
  border-top-left-radius: $radius-xs;
  font-size: $fs-subhead; line-height: $lh-normal; color: $label-primary;
  box-shadow: $shadow-card;
}

.quick {
  display: flex; flex-wrap: wrap; gap: $sp-2;
  margin: 0 0 $sp-4 (72rpx + $sp-3);
}
.quick-chip {
  padding: $sp-2 $sp-3;
  border-radius: $radius-pill;
  background: $brand-primary-wash; color: $brand-primary;
  font-size: $fs-footnote;
  &--hover { opacity: 0.6; }
}

.row {
  display: flex; margin-bottom: $sp-3;
  &.user { justify-content: flex-end; }
  &.assistant { justify-content: flex-start; }
}
.bubble {
  max-width: 82%;
  padding: $sp-3 $sp-4;
  border-radius: $radius-card;
  font-size: $fs-subhead; line-height: $lh-normal;
  &.user {
    background: $brand-primary; color: #fff;
    border-bottom-right-radius: $radius-xs;
  }
  &.assistant {
    background: $bg-primary; color: $label-primary;
    border-bottom-left-radius: $radius-xs;
    box-shadow: $shadow-card;
  }
}
.bubble-text { white-space: pre-wrap; word-break: break-word; }

.tools { display: flex; flex-wrap: wrap; gap: $sp-1; margin-bottom: $sp-2; }
.tool-chip {
  font-size: $fs-caption-2; padding: 2rpx $sp-2;
  border-radius: $radius-xs;
  background: $fill-quaternary; color: $label-secondary;
  &.running { color: $brand-primary; background: $brand-primary-wash; }
  &.failed  { color: $danger-fg; background: $danger-bg; }
}

.typing { display: flex; gap: 8rpx; padding: 6rpx 0; }
.dot {
  width: 12rpx; height: 12rpx; border-radius: 50%;
  background: $label-tertiary;
  animation: blink 1.2s infinite ease-in-out;
  &:nth-child(2) { animation-delay: 0.2s; }
  &:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }

.err { display: flex; align-items: center; gap: $sp-3; margin-top: $sp-1; }
.err-text { font-size: $fs-footnote; color: $danger-fg; }
.err-retry { font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-medium; }

/* ===== 输入区 ===== */
.composer {
  background: $bg-primary;
  border-top: $stroke-hairline solid $separator;
  padding: $sp-2 $sp-4;
  padding-bottom: #{"calc(#{$sp-2} + env(safe-area-inset-bottom))"};
}
.disclaimer {
  display: block;
  font-size: $fs-caption-2; color: $label-tertiary;
  text-align: center; margin-bottom: $sp-2;
}
.composer-row { display: flex; align-items: center; gap: $sp-2; }
.composer-input {
  flex: 1; height: 76rpx;
  padding: 0 $sp-4;
  border-radius: $radius-pill;
  background: $fill-tertiary;
  font-size: $fs-subhead; color: $label-primary;
}
.send-btn {
  flex: none; margin: 0;
  height: 76rpx; line-height: 76rpx; padding: 0 $sp-4;
  border-radius: $radius-pill;
  background: $brand-primary; color: #fff;
  font-size: $fs-subhead; font-weight: $fw-semibold;
  &::after { border: none; }
  &[disabled] { background: $fill-secondary; color: $label-tertiary; }
  &.stop { background: $fill-secondary; color: $label-primary; }
}
</style>
