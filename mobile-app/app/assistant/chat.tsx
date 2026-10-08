import { useRef, useState } from 'react';
import {
  View, Text, TextInput, Pressable, Image, StyleSheet,
  FlatList, KeyboardAvoidingView, Platform,
} from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { chatStream, type ChatHandle } from '@/api/assistant';

interface Msg {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  error?: string;
}

export default function AssistantChatScreen() {
  const params = useLocalSearchParams<{ taskId?: string; paragraphIdx?: string }>();
  const taskId = params.taskId ? Number(params.taskId) : undefined;
  // 从报告页某一段进来：预填首问，用户可直接发
  const prefill = params.paragraphIdx != null && params.paragraphIdx !== '' ? `为什么第 ${Number(params.paragraphIdx) + 1} 段像 AI？` : '';

  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState(prefill);
  const [streaming, setStreaming] = useState(false);
  const [conversationId, setConversationId] = useState('');
  const handleRef = useRef<ChatHandle | null>(null);
  const listRef = useRef<FlatList<Msg>>(null);

  function send(text: string) {
    const t = text.trim();
    if (!t || streaming) return;
    setMessages((prev) => [...prev, { role: 'user', text: t }]);
    const reply: Msg = { role: 'assistant', text: '', streaming: true };
    setMessages((prev) => [...prev, reply]);
    setStreaming(true);

    handleRef.current = chatStream(
      {
        message: t,
        conversationId: conversationId || undefined,
        taskId,
        clientContext: { platform: 'rn', page: 'assistant/chat' },
      },
      {
        onEvent: (event, data) => {
          switch (event) {
            case 'meta':
              if (data?.conversationId) setConversationId(data.conversationId);
              break;
            case 'token':
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === 'assistant') last.text += data?.delta || '';
                return next;
              });
              break;
            case 'error':
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === 'assistant') last.error = data?.message || '小白出了点问题，稍后再试';
                return next;
              });
              break;
          }
        },
        onError: (err) =>
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.role === 'assistant') last.error = err.message || '网络异常';
            return next;
          }),
      },
    );

    handleRef.current.done.finally(() => {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === 'assistant') {
          last.streaming = false;
          if (!last.text && !last.error) last.error = '小白没有返回内容，再试一次';
        }
        return next;
      });
      setStreaming(false);
    });
  }

  const isEmpty = messages.length === 0;

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.flex}>
        {isEmpty ? (
          <View style={styles.empty}>
            <Image source={require('../../assets/xiaobai.gif')} style={styles.avatar} />
            <Text style={styles.title}>嗨，我是小白</Text>
            <Text style={styles.subtitle}>检测结果看不懂、不知道怎么改，都可以直接问我。</Text>
          </View>
        ) : (
          <FlatList
            ref={listRef}
            data={messages}
            keyExtractor={(_, i) => String(i)}
            contentContainerStyle={styles.list}
            onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
            renderItem={({ item }) => (
              <View style={[styles.row, item.role === 'user' ? styles.rowUser : styles.rowAssistant]}>
                {item.role === 'assistant' && (
                  <Image source={require('../../assets/xiaobai.gif')} style={styles.avatarSm} />
                )}
                <View style={[styles.bubble, item.role === 'user' ? styles.bubbleUser : styles.bubbleAssistant]}>
                  <Text style={item.role === 'user' ? styles.textUser : styles.textAssistant}>
                    {item.text || (item.streaming ? '…' : '')}
                  </Text>
                  {item.error ? <Text style={styles.error}>{item.error}</Text> : null}
                </View>
              </View>
            )}
          />
        )}

        <View style={styles.composer}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder={taskId ? '问问这份报告…' : '想问点什么？'}
            placeholderTextColor="#9ca3af"
            editable={!streaming}
            onSubmitEditing={() => { send(input); setInput(''); }}
            returnKeyType="send"
          />
          <Pressable
            style={[styles.sendBtn, (!input.trim() || streaming) && styles.sendBtnDisabled]}
            disabled={!input.trim() || streaming}
            onPress={() => { send(input); setInput(''); }}
          >
            <Text style={styles.sendText}>{streaming ? '…' : '发送'}</Text>
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: '#F6F8F8' },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 32 },
  avatar: { width: 96, height: 96, borderRadius: 48 },
  avatarSm: { width: 30, height: 30, borderRadius: 15, marginRight: 8 },
  title: { fontSize: 22, fontWeight: '700', color: '#134E4A', marginTop: 16 },
  subtitle: { fontSize: 14, color: '#6b7280', marginTop: 8, textAlign: 'center' },
  list: { padding: 16, gap: 12 },
  row: { flexDirection: 'row', alignItems: 'flex-end' },
  rowUser: { justifyContent: 'flex-end' },
  rowAssistant: { justifyContent: 'flex-start' },
  bubble: { maxWidth: '80%', borderRadius: 14, padding: 12 },
  bubbleUser: { backgroundColor: '#0D9488' },
  bubbleAssistant: { backgroundColor: '#fff' },
  textUser: { color: '#fff', fontSize: 15, lineHeight: 21 },
  textAssistant: { color: '#1c1c1e', fontSize: 15, lineHeight: 21 },
  error: { color: '#FF3B30', fontSize: 12, marginTop: 4 },
  composer: { flexDirection: 'row', alignItems: 'center', padding: 12, gap: 8, backgroundColor: '#fff', borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#e5e7eb' },
  input: { flex: 1, minHeight: 40, maxHeight: 100, borderWidth: 1, borderColor: '#d1d5db', borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8, fontSize: 15 },
  sendBtn: { backgroundColor: '#0D9488', borderRadius: 20, paddingHorizontal: 18, paddingVertical: 10 },
  sendBtnDisabled: { opacity: 0.5 },
  sendText: { color: '#fff', fontWeight: '600', fontSize: 15 },
});
