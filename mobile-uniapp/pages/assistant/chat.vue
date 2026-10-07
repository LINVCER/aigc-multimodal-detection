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
 * 论文检测助手 · 对话页（重构版）
 *
 * 结构（自上而下）：
 *   导航（返回 · 身份 · 历史 · 更多）
 *   上下文 pill（当前绑定的报告 / 通用咨询，点开报告面板）
 *   消息流
 *     - 空态：问候 + 4 张能力卡（解读报告 / 即时测一段 / 答辩准备 / 申诉指导）+ 快捷问题
 *     - 对话：日期分隔 · 工具三态 chip · 分析卡 · Markdown 气泡 · 操作行（复制 / 重新生成 / 👍 👎）· 追问建议
 *     - 流式：光标 + 「停止生成」浮条；离底部较远时出「回到底部」
 *   输入区：「+」工具面板（换报告 / 粘贴测一段 / 清空）· 自增高输入 · 圆形发送
 *   面板：报告选择 · 粘贴检测 · 历史会话（右侧抽屉）
 *
 * 数据链路不变：listTasks / getTaskDetail / chatStream(SSE) / listConversations / submitFeedback
 */

const auth = useAuth()

/* ---------- 常量 ---------- */
const TOOL_ICON = {
  get_task_detail: '📊', list_my_tasks: '🗂', explain_paragraph: '🔍', detect_text: '🧪',
  get_threshold_policy: '📏', search_knowledge: '📚', create_appeal: '✍️',
}
const TOOL_DONE = {
  get_task_detail: '已读取报告', list_my_tasks: '已查看记录', explain_paragraph: '已分析段落', detect_text: '已检测',
  get_threshold_policy: '已查阈值', search_knowledge: '已查资料', create_appeal: '已提交申诉',
}
/** 空态能力卡：需要报告的卡在没绑定时会先弹报告面板 */
const ABILITIES = [
  { key: 'report', icon: '📊', title: '解读我的报告', sub: '哪几段最该先改', needTask: true },
  { key: 'paste', icon: '🧪', title: '即时测一段', sub: '粘贴文字立刻看结果', needTask: false },
  { key: 'defense', icon: '🎓', title: '答辩怎么准备', sub: '被问「是不是 AI 写的」', needTask: false, ask: '答辩前要准备哪些材料？如果被问「这段是不是 AI 写的」该怎么回答？' },
  { key: 'appeal', icon: '🚩', title: '我觉得判错了', sub: '申诉流程与证据', needTask: false, ask: '我觉得检测结果判错了，什么情况适合申诉，需要准备什么证据？' },
]
const LS_KEY = 'paperaigc_chat_state'

/* ---------- 状态 ---------- */
const taskId = ref(null)             // null = 通用咨询
const paragraphIdx = ref(null)
const conversationId = ref('')
const messages = ref([])             // { role, text, ts, tools:[], cards:[], error, streaming, rating }
const input = ref('')
const streaming = ref(false)
const welcome = ref('')
const prompts = ref([])
const scrollInto = ref('')
const statusBarHeight = ref(20)
const tasks = ref([])
const taskDetail = ref(null)
const farFromBottom = ref(false)
const toolMenuOpen = ref(false)
const reportSheet = ref(false)
const pasteSheet = ref(false)
const pasteText = ref('')
const showHistory = ref(false)
const historyList = ref([])
const loadingHistory = ref(false)
let stream = null

/* ---------- 派生 ---------- */
const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
const isEmpty = computed(() => messages.value.length === 0)
const activeTask = computed(() => tasks.value.find((t) => t.id === taskId.value) || null)
const riskParagraphs = computed(() => {
  const ps = taskDetail.value?.paragraphs || []
  return ps
    .filter((p) => !p.excluded && (p.calibratedProb ?? 0) >= 0.4)
    .sort((a, b) => (b.calibratedProb ?? 0) - (a.calibratedProb ?? 0))
    .slice(0, 6)
})
const taskBadge = computed(() => {
  const t = activeTask.value
  if (!t || t.aiRate == null) return null
  const diff = t.aiRate - t.threshold
  if (diff <= 0) return { text: '达标', cls: 'ok' }
  return { text: `超 ${diff.toFixed(1)}pp`, cls: diff <= t.threshold * 0.5 ? 'warn' : 'bad' }
})
/** 最后一条助手回复完成后，给 2 条还没问过的追问建议 */
const followUps = computed(() => {
  if (streaming.value || isEmpty.value) return []
  const last = messages.value[messages.value.length - 1]
  if (!last || last.role !== 'assistant' || !last.text) return []
  const asked = new Set(messages.value.filter((m) => m.role === 'user').map((m) => m.text))
  return prompts.value.filter((q) => !asked.has(q)).slice(0, 2)
})
const pct = (p) => `${((p ?? 0) * 100).toFixed(0)}%`

/* ---------- 持久化 ---------- */
function persist() {
  try {
    uni.setStorageSync(LS_KEY, JSON.stringify({ conversationId: conversationId.value, taskId: taskId.value, messages: messages.value }))
  } catch (e) { /* 忽略 */ }
}
function restore() {
  try {
    const raw = uni.getStorageSync(LS_KEY)
    if (!raw) return
    const s = JSON.parse(raw)
    conversationId.value = s.conversationId || ''
    taskId.value = s.taskId ?? null
    messages.value = (s.messages || []).map((m) => ({ ...m, streaming: false }))
  } catch (e) { /* 忽略 */ }
}

/* ---------- 生命周期 ---------- */
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
  } else {
    // 上传页「问助手为什么」带过来的首问（storage 传，取完即删）
    let pending = ''
    try { pending = uni.getStorageSync('pending_assistant_prompt') || ''; if (pending) uni.removeStorageSync('pending_assistant_prompt') } catch (e) { /* ignore */ }
    if (pending) send(pending)
    else scrollBottom()
  }
})
onUnload(() => { stream?.abort(); persist() })

/* ---------- 数据 ---------- */
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
    welcome.value = '嗨，我是小白。检测结果看不懂、不知道怎么改，都可以直接问我。'
  }
}
async function selectTask(id) {
  reportSheet.value = false
  if (id === taskId.value) return
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

/* ---------- 发送 ---------- */
function haptic() {
  // #ifdef MP-WEIXIN
  try { uni.vibrateShort({ type: 'light' }) } catch (e) { /* ignore */ }
  // #endif
}
function scrollBottom() {
  nextTick(() => {
    scrollInto.value = ''
    nextTick(() => { scrollInto.value = 'msg-bottom' })
  })
}
function onScroll(e) {
  const d = e.detail
  farFromBottom.value = d.scrollHeight - d.scrollTop - 1200 > 0 && d.scrollHeight > 1600
}
function onSend() {
  if (!canSend.value) return
  const text = input.value.trim()
  input.value = ''
  send(text)
}
function send(text) {
  if (streaming.value) return
  toolMenuOpen.value = false
  haptic()
  messages.value.push({ role: 'user', text, ts: Date.now() })
  const reply = { role: 'assistant', text: '', ts: Date.now(), tools: [], cards: [], error: null, streaming: true }
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
          if (!farFromBottom.value) scrollBottom()
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
    haptic()
    scrollBottom()
  })
}
function onStop() { stream?.abort() }

/** 重新生成：删掉这条回复，重发它前面的用户消息 */
function regenerate(idx) {
  if (streaming.value) return
  for (let i = idx - 1; i >= 0; i--) {
    if (messages.value[i].role === 'user') {
      const text = messages.value[i].text
      messages.value.splice(i, 2)
      send(text)
      return
    }
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
function onAbility(a) {
  if (a.key === 'report') {
    if (taskDetail.value) analyzeOverall()
    else reportSheet.value = true
    return
  }
  if (a.key === 'paste') { pasteSheet.value = true; return }
  if (a.ask) send(a.ask)
}
function submitPaste() {
  const t = pasteText.value.trim()
  if (t.length < 20) return uni.showToast({ title: '至少 20 个字', icon: 'none' })
  pasteSheet.value = false
  pasteText.value = ''
  send(`帮我测一下这段：${t.slice(0, 1600)}`)
}
function onNewChat() {
  toolMenuOpen.value = false
  if (streaming.value) stream?.abort()
  conversationId.value = ''
  messages.value = []
  streaming.value = false
  persist()
}
function onMore() {
  uni.showActionSheet({
    itemList: ['新对话', '切换报告', '清空本地暂存'],
    success: ({ tapIndex }) => {
      if (tapIndex === 0) onNewChat()
      else if (tapIndex === 1) reportSheet.value = true
      else if (tapIndex === 2) { onNewChat(); try { uni.removeStorageSync(LS_KEY) } catch (e) { /* ignore */ } uni.showToast({ title: '已清空', icon: 'none' }) }
    },
  })
}
function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/home/home' })
}

/* ---------- 消息操作 ---------- */
function copyAnswer(m) {
  uni.setClipboardData({ data: m.text, showToast: false, success: () => uni.showToast({ title: '已复制', icon: 'none' }) })
}
async function rateAnswer(idx, rating) {
  const m = messages.value[idx]
  if (!m || m.rating) return
  const q = [...messages.value.slice(0, idx)].reverse().find((x) => x.role === 'user')?.text || ''
  m.rating = rating
  persist()
  haptic()
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
function onBubbleLongPress(m, i) {
  if (m.role !== 'assistant' || !m.text) return
  uni.showActionSheet({
    itemList: ['复制', '重新生成', '有帮助 👍', '没帮助 👎'],
    success: ({ tapIndex }) => {
      if (tapIndex === 0) copyAnswer(m)
      else if (tapIndex === 1) regenerate(i)
      else if (tapIndex === 2) rateAnswer(i, 'up')
      else if (tapIndex === 3) rateAnswer(i, 'down')
    },
  })
}

/* ---------- 日期分隔 ---------- */
function dayLabel(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const same = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  if (same(d, now)) return '今天'
  const y = new Date(now); y.setDate(now.getDate() - 1)
  if (same(d, y)) return '昨天'
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
function showDayDivider(i) {
  const cur = messages.value[i]
  if (!cur?.ts) return false
  if (i === 0) return true
  const prev = messages.value[i - 1]
  return prev?.ts && dayLabel(prev.ts) !== dayLabel(cur.ts)
}

/* ---------- 历史 ---------- */
async function openHistory() {
  showHistory.value = true
  loadingHistory.value = true
  try {
    historyList.value = await listConversations(auth.userId ? Number(auth.userId) : undefined, 30)
  } catch (e) { historyList.value = [] } finally { loadingHistory.value = false }
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
      .map((m) => ({ role: m.role, text: m.content, ts: m.ts ? m.ts * 1000 : null, tools: [], cards: [], error: null, streaming: false }))
    showHistory.value = false
    persist()
    scrollBottom()
  } catch (e) { /* toast 由请求层 */ }
}
async function removeConversation(c) {
  try {
    await deleteConversation(c.conversationId)
    historyList.value = historyList.value.filter((x) => x.conversationId !== c.conversationId)
    if (conversationId.value === c.conversationId) { conversationId.value = ''; messages.value = []; persist() }
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
    <!-- ================= 导航 ================= -->
    <view class="nav" :style="{ paddingTop: statusBarHeight + 'px' }">
      <view class="nav-inner">
        <view class="nav-btn" hover-class="nav-btn--hover" @click="goBack"><text class="nav-btn-icon">‹</text></view>
        <view class="nav-center">
          <view class="nav-avatar"><image class="nav-avatar-img" src="/static/xiaobai.gif" mode="aspectFill" /><view class="nav-dot" /></view>
          <view class="nav-text">
            <text class="nav-title">小白</text>
            <text v-if="streaming" class="nav-sub">正在思考…</text>
          </view>
        </view>
        <view class="nav-actions">
          <view class="nav-btn" hover-class="nav-btn--hover" @click="openHistory"><text class="nav-btn-icon sm">🕘</text></view>
          <view class="nav-btn" hover-class="nav-btn--hover" @click="onMore"><text class="nav-btn-icon">⋯</text></view>
        </view>
      </view>
    </view>

    <!-- ================= 上下文 pill ================= -->
    <view class="ctx-wrap">
      <view class="ctx" :class="{ bound: activeTask }" hover-class="ctx--hover" @click="reportSheet = true">
        <text class="ctx-icon">{{ activeTask ? '📄' : '💬' }}</text>
        <text class="ctx-title">{{ activeTask ? activeTask.paperTitle : '通用咨询' }}</text>
        <text v-if="activeTask && activeTask.aiRate != null" class="ctx-rate" :class="taskBadge?.cls">AI {{ activeTask.aiRate.toFixed(1) }}%</text>
        <text v-if="taskBadge" class="ctx-badge" :class="taskBadge.cls">{{ taskBadge.text }}</text>
        <text class="ctx-switch">{{ activeTask ? '切换' : '选报告' }} ›</text>
      </view>
      <!-- 绑定报告：高风险段 chips 一行横滑 -->
      <scroll-view v-if="activeTask && taskDetail && riskParagraphs.length" class="ctx-chips" scroll-x :show-scrollbar="false">
        <view class="ctx-chips-inner">
          <view class="chip primary" hover-class="chip--hover" @click="analyzeOverall"><text>📊 整体怎么看</text></view>
          <view
            v-for="p in riskParagraphs" :key="p.paragraphIdx"
            class="chip" :class="(p.calibratedProb ?? 0) >= 0.7 ? 'red' : 'yellow'"
            hover-class="chip--hover" @click="analyzeParagraph(p.paragraphIdx)"
          ><text>段 {{ p.paragraphIdx + 1 }} · {{ pct(p.calibratedProb) }}</text></view>
        </view>
      </scroll-view>
    </view>

    <!-- ================= 消息流 ================= -->
    <scroll-view class="msgs" scroll-y :scroll-into-view="scrollInto" scroll-with-animation @scroll="onScroll" @tap="toolMenuOpen = false">
      <view class="msgs-inner">
        <!-- 空态 -->
        <view v-if="isEmpty" class="empty">
          <view class="hero">
            <image class="hero-orb" src="/static/xiaobai.gif" mode="aspectFill" />
            <text class="hero-title">{{ activeTask ? '这份报告，想从哪聊起？' : '你好，我是小白' }}</text>
            <text class="hero-sub">{{ welcome }}</text>
          </view>
          <view class="abilities">
            <view v-for="a in ABILITIES" :key="a.key" class="ability" hover-class="ability--hover" @click="onAbility(a)">
              <text class="ability-icon">{{ a.icon }}</text>
              <text class="ability-title">{{ a.title }}</text>
              <text class="ability-sub">{{ a.sub }}</text>
            </view>
          </view>
          <view v-if="prompts.length" class="quick">
            <text class="quick-label">大家常问</text>
            <view v-for="q in prompts" :key="q" class="quick-item" hover-class="quick-item--hover" @click="send(q)">
              <text class="quick-text">{{ q }}</text><text class="quick-arrow">›</text>
            </view>
          </view>
        </view>

        <!-- 对话 -->
        <template v-for="(m, i) in messages" :key="i">
          <view v-if="showDayDivider(i)" class="day"><text>{{ dayLabel(m.ts) }}</text></view>
          <view class="row" :class="m.role">
            <image v-if="m.role === 'assistant'" class="row-avatar" src="/static/xiaobai.gif" mode="aspectFill" />
            <view class="bubble" :class="m.role" @longpress="onBubbleLongPress(m, i)">
              <!-- 工具三态 -->
              <view v-if="m.role === 'assistant' && m.tools?.length" class="tools">
                <view v-for="(t, k) in m.tools" :key="k" class="tool" :class="t.status">
                  <text class="tool-icon">{{ TOOL_ICON[t.name] || '🔧' }}</text>
                  <text class="tool-text">{{ t.status === 'done' ? (TOOL_DONE[t.name] || t.label) : t.status === 'failed' ? t.label + '失败' : t.label }}</text>
                  <view v-if="t.status === 'running'" class="spin" />
                  <text v-else class="tool-mark">{{ t.status === 'done' ? '✓' : '✕' }}</text>
                </view>
              </view>
              <AssistantAnalysisCard v-for="(c, k) in (m.cards || [])" :key="'c' + k" :name="c.name" :data="c.data" />
              <view v-if="m.text && m.role === 'assistant'" class="md-wrap">
                <rich-text class="bubble-md" :nodes="renderMarkdown(m.text)" user-select />
                <text v-if="m.streaming" class="caret">▍</text>
              </view>
              <text v-else-if="m.text" class="bubble-text" user-select>{{ m.text }}</text>
              <view v-else-if="m.streaming && !m.error" class="typing"><view class="dot" /><view class="dot" /><view class="dot" /></view>
              <view v-if="m.error" class="err">
                <text class="err-text">{{ m.error }}</text>
                <text class="err-retry" @click="regenerate(i)">重试</text>
              </view>
              <!-- 操作行 -->
              <view v-if="m.role === 'assistant' && m.text && !m.streaming" class="actions">
                <text class="act" @click="copyAnswer(m)">复制</text>
                <text class="act" @click="regenerate(i)">重新生成</text>
                <view class="act-spacer" />
                <text class="act icon" :class="{ on: m.rating === 'up', off: m.rating && m.rating !== 'up' }" @click="rateAnswer(i, 'up')">👍</text>
                <text class="act icon" :class="{ on: m.rating === 'down', off: m.rating && m.rating !== 'down' }" @click="rateAnswer(i, 'down')">👎</text>
              </view>
            </view>
          </view>
        </template>

        <!-- 追问建议 -->
        <view v-if="followUps.length" class="followups">
          <view v-for="q in followUps" :key="q" class="followup" hover-class="followup--hover" @click="send(q)"><text>{{ q }}</text></view>
        </view>

        <view id="msg-bottom" class="bottom-anchor" />
      </view>
    </scroll-view>

    <!-- 浮条：停止生成 / 回到底部 -->
    <view v-if="streaming" class="float stop" @click="onStop"><view class="stop-sq" /><text>停止生成</text></view>
    <view v-else-if="farFromBottom" class="float down" @click="scrollBottom"><text>↓ 回到底部</text></view>

    <!-- ================= 输入区 ================= -->
    <view class="composer">
      <view v-if="toolMenuOpen" class="toolmenu">
        <view class="toolmenu-item" hover-class="toolmenu-item--hover" @click="reportSheet = true; toolMenuOpen = false"><text class="toolmenu-icon">📄</text><text>换报告</text></view>
        <view class="toolmenu-item" hover-class="toolmenu-item--hover" @click="pasteSheet = true; toolMenuOpen = false"><text class="toolmenu-icon">🧪</text><text>粘贴测一段</text></view>
        <view class="toolmenu-item" hover-class="toolmenu-item--hover" @click="openHistory(); toolMenuOpen = false"><text class="toolmenu-icon">🕘</text><text>历史对话</text></view>
        <view class="toolmenu-item" hover-class="toolmenu-item--hover" @click="onNewChat"><text class="toolmenu-icon">✨</text><text>新对话</text></view>
      </view>
      <view class="composer-row">
        <view class="plus" :class="{ open: toolMenuOpen }" hover-class="plus--hover" @click="toolMenuOpen = !toolMenuOpen"><text>+</text></view>
        <view class="input-wrap">
          <textarea
            v-model="input" class="composer-input" auto-height :maxlength="2000"
            :placeholder="activeTask ? '问问这份报告…' : '想问点什么？'"
            :cursor-spacing="20" :adjust-position="true" :show-confirm-bar="false"
            confirm-type="send" :disabled="streaming" @confirm="onSend" @focus="toolMenuOpen = false"
          />
        </view>
        <view class="send" :class="{ on: canSend, busy: streaming }" hover-class="send--hover" @click="streaming ? onStop() : onSend()">
          <view v-if="streaming" class="stop-sq light" /><text v-else>↑</text>
        </view>
      </view>
      <text class="disclaimer">AI 生成内容仅供参考，不替代导师意见</text>
    </view>

    <!-- ================= 报告选择面板 ================= -->
    <view v-if="reportSheet" class="mask" @click="reportSheet = false">
      <view class="sheet" @click.stop>
        <view class="sheet-handle" />
        <view class="sheet-head"><text class="sheet-title">围绕哪份报告聊</text><text class="sheet-close" @click="reportSheet = false">✕</text></view>
        <scroll-view scroll-y class="sheet-list">
          <view class="opt" :class="{ on: taskId == null }" hover-class="opt--hover" @click="selectTask(undefined)">
            <text class="opt-icon">💬</text>
            <view class="opt-main"><text class="opt-title">通用咨询</text><text class="opt-sub">不绑定报告，聊原理、政策、答辩</text></view>
            <text v-if="taskId == null" class="opt-check">✓</text>
          </view>
          <view v-for="t in tasks" :key="t.id" class="opt" :class="{ on: taskId === t.id }" hover-class="opt--hover" @click="selectTask(t.id)">
            <text class="opt-icon">📄</text>
            <view class="opt-main">
              <text class="opt-title">{{ t.paperTitle }}</text>
              <text class="opt-sub">{{ t.createdAt }} · 红线 {{ t.threshold }}%</text>
            </view>
            <text class="opt-rate" :class="t.aiRate != null && t.aiRate > t.threshold ? 'bad' : 'ok'">{{ t.aiRate == null ? '—' : t.aiRate.toFixed(1) + '%' }}</text>
            <text v-if="taskId === t.id" class="opt-check">✓</text>
          </view>
          <view v-if="!tasks.length" class="sheet-empty"><text>还没有完成的检测报告，先去上传一份</text></view>
        </scroll-view>
      </view>
    </view>

    <!-- ================= 粘贴检测面板 ================= -->
    <view v-if="pasteSheet" class="mask" @click="pasteSheet = false">
      <view class="sheet" @click.stop>
        <view class="sheet-handle" />
        <view class="sheet-head"><text class="sheet-title">粘贴一段，立刻看结果</text><text class="sheet-close" @click="pasteSheet = false">✕</text></view>
        <textarea v-model="pasteText" class="paste-input" :maxlength="1600" placeholder="粘贴 120 字以上判定更可靠；只做检测，不会改写" :adjust-position="true" :cursor-spacing="20" />
        <view class="paste-foot">
          <text class="paste-count">{{ pasteText.length }} / 1600</text>
          <button class="paste-btn" :disabled="pasteText.trim().length < 20" @click="submitPaste">检测并解读</button>
        </view>
      </view>
    </view>

    <!-- ================= 历史抽屉 ================= -->
    <view v-if="showHistory" class="mask" @click="showHistory = false">
      <view class="drawer" @click.stop>
        <view class="drawer-head"><text class="drawer-title">历史对话</text><text class="drawer-sub">保留 7 天</text><text class="sheet-close" @click="showHistory = false">✕</text></view>
        <scroll-view scroll-y class="drawer-list">
          <view v-if="loadingHistory" class="sheet-empty"><text>加载中…</text></view>
          <view v-else-if="!historyList.length" class="sheet-empty"><text>暂无历史对话</text></view>
          <view v-for="c in historyList" :key="c.conversationId" class="hist" :class="{ on: c.conversationId === conversationId }" hover-class="hist--hover" @click="resumeConversation(c)">
            <view class="hist-main">
              <text class="hist-title">{{ c.title || '（无标题）' }}</text>
              <text class="hist-meta">{{ formatTime(c.updatedAt) }} · {{ c.turns }} 轮<template v-if="c.taskId"> · 报告 #{{ c.taskId }}</template></text>
            </view>
            <text class="hist-del" @click.stop="removeConversation(c)">删除</text>
          </view>
        </scroll-view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  height: 100vh; display: flex; flex-direction: column; position: relative;
  background: linear-gradient(180deg, #EEF4FF 0%, $bg-grouped-primary 240rpx);
}

/* ===== 导航 ===== */
.nav { flex: none; @include backdrop-blur($blur-material, rgba(255, 255, 255, 0.78)); border-bottom: $stroke-hairline solid $separator; z-index: $z-navbar; }
.nav-inner { height: 96rpx; padding: 0 $sp-3; display: flex; align-items: center; justify-content: space-between; }
.nav-btn { width: 68rpx; height: 68rpx; border-radius: $radius-pill; display: flex; align-items: center; justify-content: center; &--hover { background: $fill-quaternary; } }
.nav-btn-icon { font-size: $fs-title-1; color: $label-primary; line-height: 1; &.sm { font-size: $fs-title-3; } }
.nav-center { flex: 1; min-width: 0; display: flex; align-items: center; gap: $sp-2; justify-content: center; }
.nav-avatar {
  position: relative; width: 60rpx; height: 60rpx; border-radius: $radius-pill;
  overflow: hidden;
}
.nav-avatar-img { width: 100%; height: 100%; }
.nav-dot { position: absolute; right: -2rpx; bottom: -2rpx; width: 16rpx; height: 16rpx; border-radius: 50%; background: $success-solid; border: 3rpx solid #fff; }
.nav-text { display: flex; flex-direction: column; }
.nav-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; line-height: 1.2; }
.nav-sub { font-size: $fs-caption-2; color: $label-secondary; }
.nav-actions { display: flex; }

/* ===== 上下文 pill ===== */
.ctx-wrap { flex: none; padding: $sp-2 $sp-4 0; }
.ctx {
  display: flex; align-items: center; gap: $sp-2;
  height: 76rpx; padding: 0 $sp-3 0 $sp-3;
  border-radius: $radius-pill; background: $bg-primary;
  box-shadow: $shadow-card; border: $stroke-hairline solid $separator;
  &.bound { border-color: rgba(0, 122, 255, 0.25); }
  &--hover { opacity: 0.8; }
}
.ctx-icon { flex: none; font-size: $fs-footnote; }
.ctx-title { flex: 1; min-width: 0; font-size: $fs-footnote; font-weight: $fw-medium; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.ctx-rate { flex: none; font-size: $fs-caption-2; font-weight: $fw-semibold; font-variant-numeric: tabular-nums; &.ok { color: $success-fg; } &.warn { color: $warning-fg; } &.bad { color: $danger-fg; } }
.ctx-badge { flex: none; font-size: $fs-caption-2; font-weight: $fw-semibold; padding: 2rpx $sp-2; border-radius: $radius-pill; &.ok { background: $success-bg; color: $success-fg; } &.warn { background: $warning-bg; color: $warning-fg; } &.bad { background: $danger-bg; color: $danger-fg; } }
.ctx-switch { flex: none; font-size: $fs-caption-1; color: $brand-primary; font-weight: $fw-medium; }
.ctx-chips { margin-top: $sp-2; white-space: nowrap; }
.ctx-chips-inner { display: inline-flex; gap: $sp-2; padding-bottom: 2rpx; }
.chip {
  display: inline-flex; align-items: center; flex: none;
  padding: 10rpx $sp-3; border-radius: $radius-pill;
  background: $bg-primary; color: $label-primary; border: $stroke-hairline solid $separator; font-size: $fs-footnote;
  &--hover { opacity: 0.6; }
  &.primary { background: $brand-primary; color: #fff; border-color: $brand-primary; font-weight: $fw-medium; }
  &.red { color: $danger-fg; border-color: rgba(255, 59, 48, 0.35); background: rgba(255, 59, 48, 0.06); }
  &.yellow { color: $warning-fg; border-color: rgba(255, 149, 0, 0.35); background: rgba(255, 149, 0, 0.08); }
}

/* ===== 消息流 ===== */
.msgs { flex: 1; min-height: 0; }
.msgs-inner { padding: $sp-3 $sp-4 $sp-4; }
.bottom-anchor { height: 2rpx; }

/* 空态 */
.empty { padding-top: $sp-6; }
.hero { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 0 $sp-4 $sp-6; }
.hero-orb {
  width: 128rpx; height: 128rpx; border-radius: $radius-pill;
  box-shadow: 0 16rpx 40rpx rgba(94, 92, 230, 0.28);
  margin-bottom: $sp-4;
}
.hero-title { font-size: $fs-title-2; font-weight: $fw-bold; color: $label-primary; letter-spacing: $tracking-tight; }
.hero-sub { font-size: $fs-subhead; color: $label-secondary; line-height: $lh-normal; margin-top: $sp-2; }
.abilities { display: grid; grid-template-columns: 1fr 1fr; gap: $sp-3; }
.ability {
  @include card; padding: $sp-4 $sp-4 $sp-3;
  display: flex; flex-direction: column; gap: 4rpx;
  &--hover { transform: scale(0.98); background: $fill-quaternary; }
}
.ability-icon { font-size: 44rpx; margin-bottom: $sp-1; }
.ability-title { font-size: $fs-subhead; font-weight: $fw-semibold; color: $label-primary; }
.ability-sub { font-size: $fs-caption-1; color: $label-secondary; }
.quick { margin-top: $sp-6; }
.quick-label { display: block; font-size: $fs-caption-1; color: $label-secondary; text-transform: uppercase; letter-spacing: $tracking-wide; margin: 0 $sp-2 $sp-2; }
.quick-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: $sp-3 $sp-4; margin-bottom: $sp-2;
  border-radius: $radius-lg; background: $bg-primary; box-shadow: $shadow-card;
  &--hover { background: $fill-quaternary; }
}
.quick-text { font-size: $fs-subhead; color: $label-primary; }
.quick-arrow { color: $label-tertiary; font-size: $fs-title-3; }

/* 对话 */
.day { display: flex; justify-content: center; margin: $sp-3 0; text { font-size: $fs-caption-2; color: $label-tertiary; background: $fill-quaternary; padding: 2rpx $sp-3; border-radius: $radius-pill; } }
.row { display: flex; align-items: flex-end; gap: $sp-2; margin-bottom: $sp-3; &.user { justify-content: flex-end; } }
.row-avatar {
  flex: none; width: 52rpx; height: 52rpx; border-radius: $radius-pill;
  background: $brand-gradient-vivid; color: #fff; font-size: 18rpx; font-weight: $fw-bold;
  display: flex; align-items: center; justify-content: center; margin-bottom: 6rpx;
}
.bubble {
  max-width: 84%; padding: $sp-3 $sp-4; border-radius: $radius-card;
  font-size: $fs-subhead; line-height: $lh-normal;
  &.user { background: $brand-primary; color: #fff; border-bottom-right-radius: $radius-xs; }
  &.assistant { background: $bg-primary; color: $label-primary; border-bottom-left-radius: $radius-xs; box-shadow: $shadow-card; min-width: 160rpx; }
}
.bubble-text { white-space: pre-wrap; word-break: break-word; }
.md-wrap { position: relative; }
.bubble-md { display: block; word-break: break-word; line-height: $lh-normal; }
.caret { color: $brand-primary; animation: blink 1s steps(2) infinite; }
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
  font-size: $fs-caption-2; padding: 4rpx $sp-2; border-radius: $radius-pill;
  background: $fill-quaternary; color: $label-secondary;
  &.running { color: $brand-primary; background: $brand-primary-wash; }
  &.done { color: $success-fg; background: $success-bg; }
  &.failed { color: $danger-fg; background: $danger-bg; }
}
.spin { width: 18rpx; height: 18rpx; border-radius: 50%; border: 3rpx solid currentColor; border-right-color: transparent; animation: spin .8s linear infinite; }
.tool-mark { font-weight: $fw-bold; }
@keyframes spin { to { transform: rotate(360deg); } }
.typing { display: flex; gap: 8rpx; padding: 6rpx 0; }
.dot { width: 12rpx; height: 12rpx; border-radius: 50%; background: $label-tertiary; animation: blink 1.2s infinite ease-in-out; &:nth-child(2) { animation-delay: 0.2s; } &:nth-child(3) { animation-delay: 0.4s; } }
@keyframes blink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
.err { display: flex; align-items: center; gap: $sp-3; margin-top: $sp-1; }
.err-text { font-size: $fs-footnote; color: $danger-fg; }
.err-retry { font-size: $fs-footnote; color: $brand-primary; font-weight: $fw-medium; }
.actions { display: flex; align-items: center; gap: $sp-3; margin-top: $sp-2; padding-top: $sp-2; border-top: $stroke-hairline solid $separator; }
.act { font-size: $fs-caption-1; color: $label-secondary; &.icon { font-size: $fs-footnote; } &.on { color: $brand-primary; } &.off { opacity: 0.3; } }
.act-spacer { flex: 1; }

.followups { display: flex; flex-wrap: wrap; gap: $sp-2; margin: 0 0 $sp-3 (52rpx + $sp-2); }
.followup {
  padding: 10rpx $sp-3; border-radius: $radius-pill;
  background: $brand-primary-wash; color: $brand-primary; font-size: $fs-footnote;
  border: $stroke-hairline solid rgba(0, 122, 255, 0.2);
  &--hover { opacity: 0.6; }
}

/* 浮条 */
.float {
  position: absolute; left: 50%; transform: translateX(-50%);
  bottom: #{"calc(200rpx + env(safe-area-inset-bottom))"};
  z-index: $z-sticky;
  display: flex; align-items: center; gap: $sp-2;
  padding: $sp-2 $sp-4; border-radius: $radius-pill;
  font-size: $fs-footnote; font-weight: $fw-medium;
  @include backdrop-blur($blur-material, rgba(255, 255, 255, 0.85));
  box-shadow: $shadow-lift; border: $stroke-hairline solid $separator;
  &.stop { color: $danger-fg; }
  &.down { color: $brand-primary; }
}
.stop-sq { width: 18rpx; height: 18rpx; border-radius: 4rpx; background: $danger-fg; &.light { background: #fff; } }

/* ===== 输入区 ===== */
.composer {
  flex: none; position: relative;
  @include backdrop-blur($blur-material, rgba(255, 255, 255, 0.86));
  border-top: $stroke-hairline solid $separator;
  padding: $sp-2 $sp-3; padding-bottom: #{"calc(#{$sp-2} + env(safe-area-inset-bottom))"};
}
.toolmenu {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: $sp-2;
  padding: $sp-2 $sp-1 $sp-3;
}
.toolmenu-item {
  display: flex; flex-direction: column; align-items: center; gap: 6rpx;
  padding: $sp-3 0; border-radius: $radius-md; background: $bg-primary; box-shadow: $shadow-card;
  font-size: $fs-caption-1; color: $label-primary;
  &--hover { background: $fill-quaternary; }
}
.toolmenu-icon { font-size: 40rpx; }
.composer-row { display: flex; align-items: flex-end; gap: $sp-2; }
.plus {
  flex: none; width: 76rpx; height: 76rpx; border-radius: $radius-pill;
  background: $fill-tertiary; color: $label-primary; font-size: $fs-title-2; line-height: 1;
  display: flex; align-items: center; justify-content: center;
  transition: transform .2s;
  &.open { transform: rotate(45deg); background: $brand-primary-wash; color: $brand-primary; }
  &--hover { opacity: 0.7; }
}
.input-wrap { flex: 1; min-height: 76rpx; display: flex; align-items: center; padding: 14rpx $sp-4; border-radius: 38rpx; background: $fill-tertiary; }
.composer-input { width: 100%; min-height: 44rpx; max-height: 240rpx; font-size: $fs-subhead; color: $label-primary; line-height: 44rpx; }
.send {
  flex: none; width: 76rpx; height: 76rpx; border-radius: $radius-pill;
  background: $fill-secondary; color: $label-tertiary; font-size: $fs-title-3; font-weight: $fw-bold;
  display: flex; align-items: center; justify-content: center;
  transition: background .15s;
  &.on { background: $brand-primary; color: #fff; box-shadow: 0 6rpx 16rpx rgba(0, 122, 255, 0.3); }
  &.busy { background: $danger-solid; }
  &--hover { opacity: 0.85; }
}
.disclaimer { display: block; font-size: $fs-caption-2; color: $label-tertiary; text-align: center; margin-top: $sp-2; }

/* ===== 面板 ===== */
.mask { position: fixed; left: 0; right: 0; top: 0; bottom: 0; background: rgba(0, 0, 0, 0.4); z-index: $z-sheet; display: flex; align-items: flex-end; }
.sheet {
  width: 100%; max-height: 80vh; display: flex; flex-direction: column;
  background: $bg-primary; border-radius: $radius-sheet $radius-sheet 0 0;
  padding: $sp-2 $sp-4; padding-bottom: #{"calc(#{$sp-4} + env(safe-area-inset-bottom))"};
}
.sheet-handle { width: 72rpx; height: 8rpx; border-radius: $radius-pill; background: $fill-primary; margin: $sp-1 auto $sp-3; }
.sheet-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: $sp-2; }
.sheet-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.sheet-close { color: $label-tertiary; font-size: $fs-body; padding: 0 $sp-1; }
.sheet-list { flex: 1; min-height: 0; max-height: 60vh; }
.sheet-empty { text-align: center; color: $label-tertiary; font-size: $fs-footnote; padding: $sp-8 0; }
.opt {
  display: flex; align-items: center; gap: $sp-3;
  padding: $sp-3; border-radius: $radius-lg; margin-bottom: $sp-1;
  &.on { background: $brand-primary-wash; }
  &--hover { background: $fill-quaternary; }
}
.opt-icon { flex: none; font-size: $fs-title-3; }
.opt-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2rpx; }
.opt-title { font-size: $fs-subhead; font-weight: $fw-medium; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.opt-sub { font-size: $fs-caption-2; color: $label-secondary; }
.opt-rate { flex: none; font-size: $fs-footnote; font-weight: $fw-semibold; font-variant-numeric: tabular-nums; &.ok { color: $success-fg; } &.bad { color: $danger-fg; } }
.opt-check { flex: none; color: $brand-primary; font-weight: $fw-bold; }
.paste-input { width: 100%; height: 320rpx; padding: $sp-3; border-radius: $radius-md; background: $fill-tertiary; font-size: $fs-subhead; color: $label-primary; line-height: $lh-normal; }
.paste-foot { display: flex; align-items: center; justify-content: space-between; margin-top: $sp-3; }
.paste-count { font-size: $fs-caption-1; color: $label-tertiary; }
.paste-btn {
  margin: 0; height: 76rpx; line-height: 76rpx; padding: 0 $sp-5; border-radius: $radius-pill;
  background: $brand-primary; color: #fff; font-size: $fs-subhead; font-weight: $fw-semibold;
  &::after { border: none; }
  &[disabled] { background: $fill-secondary; color: $label-tertiary; }
}

/* 历史抽屉：右侧滑入 */
.mask .drawer {
  margin-left: auto; width: 78%; height: 100%;
  background: $bg-primary; display: flex; flex-direction: column;
  padding-top: #{"calc(#{$sp-3} + env(safe-area-inset-top))"};
  box-shadow: $shadow-modal;
  animation: slidein .22s cubic-bezier(0.32, 0.72, 0, 1);
}
@keyframes slidein { from { transform: translateX(100%); } to { transform: translateX(0); } }
.drawer-head { display: flex; align-items: baseline; gap: $sp-2; padding: $sp-3 $sp-4; border-bottom: $stroke-hairline solid $separator; }
.drawer-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.drawer-sub { flex: 1; font-size: $fs-caption-1; color: $label-secondary; }
.drawer-list { flex: 1; min-height: 0; padding: $sp-2 $sp-3; }
.hist {
  display: flex; align-items: center; gap: $sp-2;
  padding: $sp-3; border-radius: $radius-lg; margin-bottom: $sp-1;
  &.on { background: $brand-primary-wash; }
  &--hover { background: $fill-quaternary; }
}
.hist-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2rpx; }
.hist-title { font-size: $fs-subhead; font-weight: $fw-medium; color: $label-primary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.hist-meta { font-size: $fs-caption-2; color: $label-secondary; }
.hist-del { flex: none; font-size: $fs-caption-1; color: $danger-fg; }
</style>
