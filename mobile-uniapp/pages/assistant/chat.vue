<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { chatStream, getQuickPrompts } from '@/api/assistant'
import { useAuth } from '@/store/auth'

/*
 * 论文检测助手 · 对话页
 * 入口：task/detail「问助手」（带 taskId / paragraphIdx）· 四个 tab 页右下角 FAB（不带任务）
 * 协议：SSE meta / token / tool_call / tool_result / done / error，见 api/assistant.js
 */

const auth = useAuth()

const taskId = ref(null)
const paragraphIdx = ref(null)
const conversationId = ref('')
const messages = ref([])          // { role: 'user'|'assistant', text, tools:[], error, streaming }
const input = ref('')
const streaming = ref(false)
const welcome = ref('')
const prompts = ref([])
const scrollInto = ref('')
const statusBarHeight = ref(20)

let stream = null

const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
const showQuick = computed(() => messages.value.length === 0 && prompts.value.length > 0)

onLoad(async (query) => {
  const sys = uni.getSystemInfoSync()
  statusBarHeight.value = sys.statusBarHeight || 20
  if (query?.taskId) taskId.value = Number(query.taskId)
  if (query?.paragraphIdx !== undefined && query.paragraphIdx !== '') paragraphIdx.value = Number(query.paragraphIdx)
  if (query?.conversationId) conversationId.value = query.conversationId

  try {
    const qp = await getQuickPrompts(taskId.value || undefined)
    welcome.value = qp?.welcome || ''
    prompts.value = qp?.prompts || []
  } catch (e) {
    welcome.value = '嗨，我是论文检测助手。检测结果看不懂、不知道怎么改，都可以直接问我。'
  }

  // 从「为什么这段像 AI」直达：自动发第一问
  if (taskId.value != null && paragraphIdx.value != null) {
    send(`第 ${paragraphIdx.value + 1} 段为什么会被判成像 AI？`)
  }
})

onUnmounted(() => { stream?.abort() })

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
  const reply = { role: 'assistant', text: '', tools: [], error: null, streaming: true }
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
          <text v-if="taskId" class="nav-sub">围绕报告 #{{ taskId }}</text>
        </view>
        <text class="nav-btn" @click="onNewChat">新对话</text>
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
.nav-center { display: flex; flex-direction: column; align-items: center; }
.nav-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.nav-sub { font-size: $fs-caption-2; color: $label-secondary; margin-top: 2rpx; }

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
