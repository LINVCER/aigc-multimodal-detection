<script setup lang="ts">
import { ref, computed, nextTick, watch, onBeforeUnmount } from 'vue'
import { chatStream, getQuickPrompts, type ChatHandle } from '@/api/assistant'

/**
 * 论文检测助手 · 右侧抽屉（Web 端）
 * 从 TaskDetail 头部「问助手」打开；带 taskId 作为对话默认上下文。
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

const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
const showQuick = computed(() => messages.value.length === 0 && prompts.value.length > 0)

watch(() => props.modelValue, async (open) => {
  if (!open) return
  if (!welcome.value) {
    try {
      const qp = await getQuickPrompts(props.taskId)
      welcome.value = qp.welcome
      prompts.value = qp.prompts || []
    } catch {
      welcome.value = '嗨，我是论文检测助手。检测结果看不懂、不知道怎么改，都可以直接问我。'
    }
  }
  if (props.paragraphIdx != null) {
    pendingParagraph = props.paragraphIdx
    send(`第 ${props.paragraphIdx + 1} 段为什么会被判成像 AI？`)
  }
})

onBeforeUnmount(() => handle?.abort())

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
    taskId: props.taskId,
    paragraphIdx: pendingParagraph ?? undefined,
    userId: userIdRaw ? Number(userIdRaw) : undefined,
    clientContext: { platform: 'web', page: 'TaskDetail' },
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
}
</script>

<template>
  <el-drawer v-model="visible" size="440px" :with-header="false" class="assistant-drawer">
    <div class="ad">
      <div class="ad-head">
        <div class="ad-title">
          <span class="ad-avatar">AI</span>
          <div>
            <div class="ad-name">论文检测助手</div>
            <div v-if="taskId" class="ad-sub">围绕报告 #{{ taskId }}</div>
          </div>
        </div>
        <div>
          <el-button link size="small" @click="onNewChat">新对话</el-button>
          <el-button link size="small" @click="visible = false">关闭</el-button>
        </div>
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
            :placeholder="taskId ? '问问这份报告…' : '想问点什么？'"
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
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px; border-bottom: 1px solid var(--el-border-color-lighter);
}
.ad-title { display: flex; align-items: center; gap: 10px; }
.ad-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, #5E5CE6 0%, #64D2FF 100%);
  color: #fff; font-weight: 700; font-size: 12px;
  display: inline-flex; align-items: center; justify-content: center;
}
.ad-name { font-weight: 600; font-size: 15px; }
.ad-sub { font-size: 12px; color: var(--el-text-color-secondary); }

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
