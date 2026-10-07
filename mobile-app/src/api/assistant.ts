import { http, API_BASE, MOCK_MODE } from './client';
import * as SecureStore from 'expo-secure-store';

/**
 * 论文检测助手「小白」API —— 协议见 docs/design/202610-paper-assistant-agent-research.md §3.3
 * 与 web / uniapp 共用同一后端 /api/v1/assistant/*。
 */

export interface AssistantMsg {
  role: 'user' | 'assistant';
  content: string;
}

export interface ConversationSummary {
  conversationId: string;
  title: string;
  taskId?: number;
  updatedAt: number;
  turns: number;
}

export interface ConversationDetail {
  conversationId: string;
  taskId?: number;
  messages: AssistantMsg[];
}

export interface ChatPayload {
  message: string;
  conversationId?: string;
  taskId?: number;
  paragraphIdx?: number;
  userId?: number;
  clientContext?: Record<string, unknown>;
}

export interface ChatHandlers {
  onEvent: (event: string, data: any) => void;
  onError: (err: Error) => void;
}

export interface ChatHandle {
  abort: () => void;
  done: Promise<void>;
}

/* ---------- SSE 流式对话（RN 用 XHR onprogress 解析） ---------- */

function parseSSEDelta(chunk: string, onEvent: (event: string, data: any) => void) {
  // 按行切分，SSE 事件以「event: xxx」+「data: {...}」成对出现
  let event = 'message';
  for (const raw of chunk.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      const payload = line.slice(5).trim();
      if (!payload || payload === '[DONE]') continue;
      try {
        onEvent(event, JSON.parse(payload));
      } catch {
        // 非 JSON 片段忽略
      }
    }
  }
}

export function chatStream(payload: ChatPayload, handlers: ChatHandlers): ChatHandle {
  if (MOCK_MODE) {
    // mock：走一段假回复，供离线 UI 开发
    let cancelled = false;
    const timer = setTimeout(() => {
      if (cancelled) return;
      handlers.onEvent('meta', { conversationId: `mock-${Date.now()}` });
      handlers.onEvent('token', { delta: '（离线演示）我是小白，检测结果看不懂、不知道怎么改，都可以直接问我。' });
      handlers.onEvent('done', { finishReason: 'stop' });
    }, 600);
    return {
      abort: () => { cancelled = true; clearTimeout(timer); },
      done: Promise.resolve(),
    };
  }

  const xhr = new XMLHttpRequest();
  xhr.open('POST', `${API_BASE}/api/v1/assistant/chat`);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.setRequestHeader('Accept', 'text/event-stream');

  let buffer = '';
  let settled = false;
  let resolveDone!: () => void;
  const done = new Promise<void>((res) => { resolveDone = res; });

  (async () => {
    const token = await SecureStore.getItemAsync('access_token');
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(JSON.stringify(payload));
  })();

  xhr.onprogress = () => {
    const text = xhr.responseText || '';
    if (text.length <= buffer.length) return;
    const delta = text.slice(buffer.length);
    buffer = text;
    parseSSEDelta(delta, handlers.onEvent);
  };
  xhr.onload = () => { if (!settled) { settled = true; resolveDone(); } };
  xhr.onerror = () => {
    if (!settled) { settled = true; handlers.onError(new Error('网络异常，请稍后重试')); resolveDone(); }
  };
  xhr.onabort = () => { if (!settled) { settled = true; resolveDone(); } };

  return { abort: () => xhr.abort(), done };
}

/* ---------- 会话 / 快捷问题 ---------- */

export async function listConversations(limit = 30): Promise<ConversationSummary[]> {
  if (MOCK_MODE) return [];
  const resp = await http.get('/api/v1/assistant/conversations', { params: { limit } });
  return resp.data.data;
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  const resp = await http.get(`/api/v1/assistant/conversations/${conversationId}`);
  return resp.data.data;
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await http.delete(`/api/v1/assistant/conversations/${conversationId}`);
}

export async function getQuickPrompts(taskId?: number): Promise<{ welcome: string; prompts: string[] }> {
  if (MOCK_MODE) {
    return {
      welcome: '嗨，我是小白。检测结果看不懂、不知道怎么改，都可以直接问我。',
      prompts: ['为什么这段像 AI？', '我 AI 率 22%，本科能过吗？', '哪几段最该先改？'],
    };
  }
  const resp = await http.get('/api/v1/assistant/quick-prompts', { params: taskId ? { taskId } : {} });
  return resp.data.data;
}
