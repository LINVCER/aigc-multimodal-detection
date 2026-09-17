import { useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { getTaskDetail, requestHumanize, type ParagraphResult } from '@/api/detect';

const SOURCE_LABEL: Record<string, string> = {
  human: '人类', gpt: 'GPT', claude: 'Claude', qwen: '通义千问',
  deepseek: 'DeepSeek', glm: '智谱GLM', kimi: 'Kimi', ernie: '文心', other: '其他',
};

function sentenceBg(prob: number): string {
  if (prob >= 0.7) return '#fee2e2';
  if (prob >= 0.4) return '#fef3c7';
  return 'transparent';
}

function ParagraphCard({ paragraph, taskId }: { paragraph: ParagraphResult; taskId: number }) {
  const [rewritten, setRewritten] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const isHighRisk = paragraph.calibratedProb >= 0.7;

  const humanize = async () => {
    setLoading(true);
    try {
      const text = await requestHumanize(taskId, paragraph.paragraphIdx);
      setRewritten(text);
    } catch (e) {
      Alert.alert('降 AIGC 失败', e instanceof Error ? e.message : '请稍后重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.paragraphCard}>
      <View style={styles.paragraphHeader}>
        <Text style={styles.paragraphIdx}>第 {paragraph.paragraphIdx + 1} 段</Text>
        <Text style={[styles.prob, { color: isHighRisk ? '#ef4444' : paragraph.calibratedProb >= 0.4 ? '#f59e0b' : '#10b981' }]}>
          AI 概率 {(paragraph.calibratedProb * 100).toFixed(0)}%
          {paragraph.sourceLabel && paragraph.sourceLabel !== 'human'
            ? ` · 疑似${SOURCE_LABEL[paragraph.sourceLabel] ?? paragraph.sourceLabel}`
            : ''}
        </Text>
      </View>

      {/* 句子级高亮 */}
      <Text style={styles.paragraphText}>
        {paragraph.sentences.map((s) => (
          <Text key={s.sentenceIdx} style={{ backgroundColor: sentenceBg(s.aiProb) }}>
            {s.text}
          </Text>
        ))}
      </Text>

      {isHighRisk && !rewritten && (
        <Pressable style={styles.humanizeBtn} onPress={humanize} disabled={loading}>
          {loading
            ? <ActivityIndicator size="small" color="#1a56db" />
            : <Text style={styles.humanizeBtnText}>✨ 降 AIGC 改写建议</Text>}
        </Pressable>
      )}

      {rewritten && (
        <View style={styles.rewrittenBox}>
          <Text style={styles.rewrittenLabel}>改写建议（请人工核对语义后使用）</Text>
          <Text style={styles.rewrittenText}>{rewritten}</Text>
        </View>
      )}
    </View>
  );
}

export default function TaskDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const taskId = Number(id);
  const { data, isLoading } = useQuery({
    queryKey: ['task', taskId],
    queryFn: () => getTaskDetail(taskId),
  });

  if (isLoading || !data) {
    return <View style={styles.center}><ActivityIndicator size="large" /></View>;
  }

  const pass = data.aiRate != null && data.aiRate <= data.threshold;

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      {/* 总览卡 */}
      <View style={[styles.summaryCard, { backgroundColor: pass ? '#ecfdf5' : '#fef2f2' }]}>
        <Text style={styles.summaryTitle} numberOfLines={2}>{data.paperTitle}</Text>
        <Text style={[styles.summaryRate, { color: pass ? '#10b981' : '#ef4444' }]}>
          {data.aiRate?.toFixed(1)}%
        </Text>
        <Text style={styles.summaryVerdict}>
          {pass ? `低于红线 ${data.threshold}%，达标 ✓` : `超过红线 ${data.threshold}%，建议修改后重检`}
        </Text>
      </View>

      {/* 溯源分布 */}
      <View style={styles.sourceCard}>
        <Text style={styles.sourceTitle}>疑似来源分布</Text>
        {Object.entries(data.sourceLabels)
          .sort(([, a], [, b]) => b - a)
          .map(([label, ratio]) => (
            <View key={label} style={styles.sourceRow}>
              <Text style={styles.sourceLabel}>{SOURCE_LABEL[label] ?? label}</Text>
              <View style={styles.sourceBarTrack}>
                <View style={[styles.sourceBarFill, { width: `${ratio * 100}%` }]} />
              </View>
              <Text style={styles.sourceRatio}>{(ratio * 100).toFixed(0)}%</Text>
            </View>
          ))}
      </View>

      {/* 图例 */}
      <View style={styles.legend}>
        <Text style={styles.legendItem}><Text style={{ backgroundColor: '#fee2e2' }}>　</Text> 高疑似 AI</Text>
        <Text style={styles.legendItem}><Text style={{ backgroundColor: '#fef3c7' }}>　</Text> 中等疑似</Text>
        <Text style={styles.legendItem}>无底色 = 判定人写</Text>
      </View>

      {/* 段落列表 */}
      {data.paragraphs.map((p) => (
        <ParagraphCard key={p.paragraphIdx} paragraph={p} taskId={taskId} />
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  summaryCard: { borderRadius: 12, padding: 20, alignItems: 'center' },
  summaryTitle: { fontSize: 15, fontWeight: '600', color: '#111827', textAlign: 'center' },
  summaryRate: { fontSize: 42, fontWeight: '800', marginVertical: 6 },
  summaryVerdict: { fontSize: 13, color: '#374151' },
  sourceCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 12 },
  sourceTitle: { fontSize: 14, fontWeight: '600', color: '#374151', marginBottom: 10 },
  sourceRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  sourceLabel: { width: 70, fontSize: 13, color: '#6b7280' },
  sourceBarTrack: { flex: 1, height: 8, backgroundColor: '#e5e7eb', borderRadius: 4, marginHorizontal: 8 },
  sourceBarFill: { height: 8, backgroundColor: '#1a56db', borderRadius: 4 },
  sourceRatio: { width: 40, fontSize: 12, color: '#374151', textAlign: 'right' },
  legend: { flexDirection: 'row', gap: 14, marginTop: 14, marginBottom: 6, paddingHorizontal: 4 },
  legendItem: { fontSize: 11, color: '#6b7280' },
  paragraphCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 10 },
  paragraphHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8 },
  paragraphIdx: { fontSize: 12, color: '#9ca3af' },
  prob: { fontSize: 12, fontWeight: '600' },
  paragraphText: { fontSize: 14, lineHeight: 24, color: '#111827' },
  humanizeBtn: {
    marginTop: 12, borderWidth: 1, borderColor: '#1a56db', borderRadius: 8,
    paddingVertical: 9, alignItems: 'center',
  },
  humanizeBtnText: { color: '#1a56db', fontSize: 13, fontWeight: '600' },
  rewrittenBox: { marginTop: 12, backgroundColor: '#eff6ff', borderRadius: 8, padding: 12 },
  rewrittenLabel: { fontSize: 11, color: '#1a56db', marginBottom: 6, fontWeight: '600' },
  rewrittenText: { fontSize: 14, lineHeight: 22, color: '#1e3a8a' },
});
