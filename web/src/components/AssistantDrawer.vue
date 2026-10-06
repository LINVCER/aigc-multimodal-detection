<script setup lang="ts">
import { ref, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { chatStream, getQuickPrompts, type ChatHandle } from '@/api/assistant'
import { listTasks, getTaskDetail } from '@/api/detect'
import type { DetectTask, TaskDetail } from '@/api/types'

/**
 * 论文检测助手 · 右侧抽屉（Web 端）
 * - 从 TaskDetail 头部「问助手」打开（带 taskId）；也能在任何地方打开后自行选择报告
 * - 顶部「报告选择」下拉：复用 listTasks 列出最近 DONE 报告，绑定对话上下文
 * - 绑定报告后：复用 getTaskDetail 拉段落，出「整体分析 + 高风险段落」快捷条，一键「分析原因」
 */

interface ToolChip { name: string; label: string; status: 'running' | 'done' | 'failed' }
interface Msg {
  role: 'user' | 'assistant'
  text: string
  tools?: ToolChip[]
  error?: string | null
  streaming?: boolean
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

// ---- 报告上下文（「可以选择检测报告进行对话」）----
const activeTaskId = ref<number | undefined>(undefined)   // undefined = 通用咨询
const taskOptions = ref<DetectTask[]>([])
const taskDetail = ref<TaskDetail | null>(null)
const loadingTasks = ref(false)

const activeTask = computed(() => taskOptions.value.find((t) => t.id === activeTaskId.value))
const taskTitle = computed(() => activeTask.value?.paperTitle || '')

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

function pct(prob: number | null | undefined): string {
  return `${((prob ?? 0) * 100).toFixed(0)}%`
}

onBeforeUnmount(() => handle?.abort())

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
    welcome.value = '嗨，我是论文检测助手。检测结果看不懂、不知道怎么改，都可以直接问我。'
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
  await refreshPrompts(id)
  if (id != null) {
    try {
      taskDetail.value = await getTaskDetail(id)
    } catch {
      taskDetail.value = null
    }
  }
}

function onTaskChange(v: number | undefined) {
  // el-select 清除时可能回传 '' 或 undefined，统一归一为「通用咨询」
  selectTask(v || undefined)
}

watch(() => props.modelValue, async (open) => {
  if (!open) return
  if (taskOptions.value.length === 0) await loadTasks()
  // 从 TaskDetail 打开：同步其 taskId
  if (props.taskId != null && props.taskId !== activeTaskId.value) {
    await selectTask(props.taskId)
  } else if (!welcome.value) {
    await refreshPrompts(activeTaskId.value)
  }
  // 「为什么这段像 AI」直达
  if (props.paragraphIdx != null) {
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
}
</script>

<template>
  <el-drawer v-model="visible" size="460px" :with-header="false" class="assistant-drawer">
    <div class="ad">
      <div class="ad-head">
        <div class="ad-head-top">
          <div class="ad-title">
            <span class="ad-avatar">AI</span>
            <div>
              <div class="ad-name">论文检测助手</div>
              <div v-if="activeTask" class="ad-sub">{{ activeTask.paperTitle }}</div>
              <div v-else class="ad-sub">通用咨询</div>
            </div>
          </div>
          <div class="ad-head-actions">
            <el-button link size="small" @click="onNewChat">新对话</el-button>
            <el-button link size="small" @click="visible = false">关闭</el-button>
          </div>
        </div>

        <!-- 报告选择：复用 listTasks -->
        <el-select
          v-model="activeTaskId"
          class="ad-task-select"
          size="small"
          placeholder="选择要咨询的检测报告…"
          clearable
          :loading="loadingTasks"
          @change="onTaskChange"
        >
          <el-option
            v-for="t in taskOptions"
            :key="t.id"
            :value="t.id"
            :label="t.paperTitle"
          >
            <span class="ad-opt-title">{{ t.paperTitle }}</span>
            <span class="ad-opt-rate" :class="{ over: t.aiRate != null && t.aiRate > t.threshold }">
              AI {{ t.aiRate != null ? t.aiRate.toFixed(0) + '%' : '—' }}
            </span>
          </el-option>
        </el-select>
      </div>

      <!-- 报告上下文快捷条：整体分析 + 高风险段落（「分析原因」） -->
      <div v-if="activeTask && taskDetail && riskParagraphs.length" class="ad-context">
        <el-tag round effect="plain" type="primary" class="ad-chip" @click="analyzeOverall">
          📊 整体怎么看
        </el-tag>
        <el-tag
          v-for="p in riskParagraphs"
          :key="p.paragraphIdx"
          round
          effect="plain"
          class="ad-chip"
          @click="analyzeParagraph(p.paragraphIdx)"
        >
          段 {{ p.paragraphIdx + 1 }} · {{ pct(p.calibratedProb) }}
        </el-tag>
      </div>

      <div ref="listEl" class="ad-list">
        <div class="ad-welcome">{{ welcome }}</div>

        <div v-if="showQuick" class="ad-quick">
          <el-tag v-for="q in prompts" :key="q" round effect="plain" class="ad-chip" @click="send(q)">{{ q }}</el-tag>
        </div>

        <div v-for="(m, i) in messages" :key="i" class="ad-row" :class="m.role">
          <div class="ad-bubble" :class="m.role">
            <div v-if="m.role === 'assistant' && m.tools?.length" class="ad-tools">
              <span v-for="(t, k) in m.tools" :key="k" class="ad-tool" :class="t.status">
                {{ t.status === 'running' ? '正在' : '' }}{{ t.label }}{{ t.status === 'failed' ? '（失败）' : '' }}
              </span>
            </div>
            <div v-if="m.text" class="ad-text">{{ m.text }}</div>
            <div v-else-if="m.streaming && !m.error" class="ad-typing"><i /><i /><i /></div>
            <div v-if="m.error" class="ad-err">
              <span>{{ m.error }}</span>
              <el-button link type="primary" size="small" @click="onRetry(i)">重试</el-button>
            </div>
          </div>
        </div>
      </div>

      <div class="ad-composer">
        <div class="ad-disclaimer">AI 生成内容仅供参考，不替代导师意见；助手不代写、不改写原文。</div>
        <div class="ad-input-row">
          <el-input
            v-model="input"
            :placeholder="activeTaskId ? '问问这份报告…' : '想问点什么？'"
            :disabled="streaming"
            @keyup.enter="onSend"
          />
          <el-button v-if="streaming" @click="onStop">停止</el-button>
          <el-button v-else type="primary" :disabled="!canSend" @click="onSend">发送</el-button>
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<style scoped lang="scss">
.ad { height: 100%; display: flex; flex-direction: column; }
.ad-head {
  padding: 14px 16px 12px; border-bottom: 1px solid var(--el-border-color-lighter);
}
.ad-head-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.ad-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
.ad-avatar {
  width: 36px; height: 36px; border-radius: 50%; flex: none;
  background: linear-gradient(135deg, #5E5CE6 0%, #64D2FF 100%);
  color: #fff; font-weight: 700; font-size: 12px;
  display: inline-flex; align-items: center; justify-content: center;
}
.ad-name { font-weight: 600; font-size: 15px; }
.ad-sub {
  font-size: 12px; color: var(--el-text-color-secondary);
  max-width: 230px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ad-head-actions { display: flex; gap: 4px; flex: none; }
.ad-task-select { width: 100%; }

.ad-opt-title { float: left; max-width: 300px; overflow: hidden; text-overflow: ellipsis; }
.ad-opt-rate { float: right; color: var(--el-text-color-secondary); font-size: 12px; margin-left: 8px; }
.ad-opt-rate.over { color: var(--el-color-danger); }

.ad-context {
  display: flex; flex-wrap: wrap; gap: 6px;
  padding: 10px 16px; border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}

.ad-list { flex: 1; overflow-y: auto; padding: 16px; background: var(--el-fill-color-lighter); }
.ad-welcome {
  background: #fff; border-radius: 14px; border-top-left-radius: 4px;
  padding: 12px 14px; font-size: 14px; line-height: 1.55;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  margin-bottom: 12px;
}
.ad-quick { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.ad-chip { cursor: pointer; }

.ad-row { display: flex; margin-bottom: 10px; &.user { justify-content: flex-end; } }
.ad-bubble {
  max-width: 84%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.55;
  &.user { background: var(--el-color-primary); color: #fff; border-bottom-right-radius: 4px; }
  &.assistant { background: #fff; border-bottom-left-radius: 4px; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04); }
}
.ad-text { white-space: pre-wrap; word-break: break-word; }
.ad-tools { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.ad-tool {
  font-size: 11px; padding: 1px 8px; border-radius: 4px;
  background: var(--el-fill-color); color: var(--el-text-color-secondary);
  &.running { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
  &.failed { color: var(--el-color-danger); background: var(--el-color-danger-light-9); }
}
.ad-typing {
  display: flex; gap: 4px; padding: 4px 0;
  i { width: 6px; height: 6px; border-radius: 50%; background: #c0c4cc; animation: adblink 1.2s infinite; }
  i:nth-child(2) { animation-delay: 0.2s; }
  i:nth-child(3) { animation-delay: 0.4s; }
}
@keyframes adblink { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }
.ad-err { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--el-color-danger); margin-top: 4px; }

.ad-composer { border-top: 1px solid var(--el-border-color-lighter); padding: 10px 16px 14px; }
.ad-disclaimer { font-size: 11px; color: var(--el-text-color-placeholder); text-align: center; margin-bottom: 8px; }
.ad-input-row { display: flex; gap: 8px; }
</style>
