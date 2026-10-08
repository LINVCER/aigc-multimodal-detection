import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Alert, ActivityIndicator, ScrollView } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { submitFeedback, type FeedbackCategory } from '@/api/report';

/** 意见反馈 / 结果申诉：带 taskId 进来默认申诉分类 */
const CATEGORIES: Array<{ key: FeedbackCategory; label: string; hint: string }> = [
  { key: 'appeal', label: '结果申诉', hint: '说明哪几段是自己写的、依据是什么，人工复核后在「我的反馈」回复' },
  { key: 'bug', label: 'Bug', hint: '哪个页面、做了什么、出现了什么' },
  { key: 'suggestion', label: '建议', hint: '想要什么功能、现在哪里不顺手' },
];

export default function FeedbackScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ taskId?: string }>();
  const taskId = params.taskId ? Number(params.taskId) : undefined;
  const [category, setCategory] = useState<FeedbackCategory>(taskId ? 'appeal' : 'suggestion');
  const [content, setContent] = useState('');
  const [contact, setContact] = useState('');
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (content.trim().length < 10) { Alert.alert('提示', '请至少写 10 个字'); return; }
    if (category === 'appeal' && !taskId) { Alert.alert('提示', '申诉请从报告页进入'); return; }
    setLoading(true);
    try {
      await submitFeedback({ category, content: content.trim(), taskId: category === 'appeal' ? taskId : undefined, contact: contact.trim() || undefined });
      Alert.alert('已提交', category === 'appeal' ? '人工复核后会在这里回复' : '感谢反馈', [{ text: '好', onPress: () => router.back() }]);
    } catch (e) {
      Alert.alert('提交失败', e instanceof Error ? e.message : '请稍后重试');
    } finally { setLoading(false); }
  }

  const cat = CATEGORIES.find((c) => c.key === category)!;
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 20 }} keyboardShouldPersistTaps="handled">
      <View style={styles.seg}>
        {CATEGORIES.map((c) => (
          <Pressable key={c.key} style={[styles.segBtn, category === c.key && styles.segOn]} onPress={() => setCategory(c.key)}>
            <Text style={[styles.segText, category === c.key && styles.segTextOn]}>{c.label}</Text>
          </Pressable>
        ))}
      </View>
      {taskId ? <Text style={styles.task}>关联任务 #{taskId}</Text> : null}
      <View style={styles.card}>
        <TextInput style={styles.area} multiline value={content} onChangeText={setContent} placeholder={cat.hint} textAlignVertical="top" maxLength={2000} />
        <Text style={styles.count}>{content.length}/2000</Text>
        <TextInput style={styles.input} value={contact} onChangeText={setContact} placeholder="联系方式（可选，邮箱 / 微信）" />
        <Pressable style={[styles.btn, loading && { opacity: 0.6 }]} disabled={loading} onPress={submit}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>提交</Text>}
        </Pressable>
      </View>
      <Text style={styles.note}>申诉结论只用于人工复核与改进模型，不会改动你的报告结论；不代写、不改写原文。</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  seg: { flexDirection: 'row', backgroundColor: '#e5e7eb', borderRadius: 10, padding: 3, marginBottom: 12 },
  segBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8 },
  segOn: { backgroundColor: '#fff' },
  segText: { fontSize: 14, color: '#6b7280' }, segTextOn: { color: '#111827', fontWeight: '600' },
  task: { fontSize: 12, color: '#6b7280', marginBottom: 8 },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 16 },
  area: { minHeight: 140, borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, padding: 12, fontSize: 15, lineHeight: 22 },
  count: { fontSize: 11, color: '#9ca3af', textAlign: 'right', marginTop: 4 },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14, marginTop: 10 },
  btn: { marginTop: 14, backgroundColor: '#0D9488', borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  note: { fontSize: 12, color: '#9ca3af', lineHeight: 18, marginTop: 14 },
});
