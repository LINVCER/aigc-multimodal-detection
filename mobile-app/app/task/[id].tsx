import { useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Alert, ActivityIndicator, Linking, Share } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { getTaskDetail, type ParagraphResult } from '@/api/detect';
import { reportPdfUrl, createShare } from '@/api/report';

/**
 * 检测报告：总览（AI 率 · 达标 · 凭证）→ 动作条（问小白 / 下载 PDF / 只读分享 / 申诉）→ 溯源 → 段落（高风险段可问小白）
 * 与 web / uniapp 同一套入口；不再提供改写按钮（平台不代写不改写）
 */
const SOURCE_LABEL: Record<string, string> = {
  human: '人类', gpt: 'GPT', claude: 'Claude', qwen: '通义千问',
  deepseek: 'DeepSeek', glm: '智谱GLM', kimi: 'Kimi', ernie: '文心', other: '其他',
};
const EXCLUDE_LABEL: Record<string, string> = { reference: '参考文献', acknowledgement: '致谢', appendix: '附录', sectionTitle: '章节标题', caption: '图表标题' };

function sentenceBg(prob: number): string {
  if (prob >= 0.7) return '#fee2e2';
  if (prob >= 0.4) return '#fef3c7';
  return 'transparent';
}
function probColor(p: number) { return p >= 0.7 ? '#ef4444' : p >= 0.4 ? '#f59e0b' : '#10b981'; }

function ParagraphCard({ paragraph, taskId }: { paragraph: ParagraphResult; taskId: number }) {
  const router = useRouter();
  const prob = paragraph.calibratedProb ?? 0;
  if (paragraph.excluded) {
    return (
      <View style={[styles.paragraphCard, { opacity: 0.7 }]}>
        <View style={styles.paragraphHeader}>
          <Text style={styles.paragraphIdx}>第 {paragraph.paragraphIdx + 1} 段</Text>
          <Text style={styles.excluded}>未参与计算 · {EXCLUDE_LABEL[paragraph.excludeReason || ''] || '非正文'}</Text>
        </View>
        <Text style={[styles.paragraphText, { color: '#6b7280' }]}>{paragraph.text}</Text>
      </View>
    );
  }
  return (
    <View style={styles.paragraphCard}>
      <View style={styles.paragraphHeader}>
        <Text style={styles.paragraphIdx}>第 {paragraph.paragraphIdx + 1} 段{paragraph.sectionName ? ` · ${paragraph.sectionName}` : ''}</Text>
        <Text style={[styles.prob, { color: probColor(prob) }]}>
          {(prob * 100).toFixed(0)}%{paragraph.sourceLabel && paragraph.sourceLabel !== 'human' ? ` · 疑似${SOURCE_LABEL[paragraph.sourceLabel] ?? paragraph.sourceLabel}` : ''}
        </Text>
      </View>
      <Text style={styles.paragraphText}>
        {paragraph.sentences?.length
          ? paragraph.sentences.map((s) => <Text key={s.sentenceIdx} style={{ backgroundColor: sentenceBg(s.aiProb) }}>{s.text}</Text>)
          : paragraph.text}
      </Text>
      {prob >= 0.4 && (
        <Pressable style={styles.askBtn} onPress={() => router.push({ pathname: '/assistant/chat', params: { taskId: String(taskId), paragraphIdx: String(paragraph.paragraphIdx) } })}>
          <Text style={styles.askBtnText}>💬 为什么这段像 AI？</Text>
        </Pressable>
      )}
    </View>
  );
}

export default function TaskDetailScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const taskId = Number(id);
  const { data, isLoading } = useQuery({ queryKey: ['task', taskId], queryFn: () => getTaskDetail(taskId) });
  const [sharing, setSharing] = useState(false);

  if (isLoading || !data) {
    return <View style={styles.center}><ActivityIndicator size="large" /></View>;
  }
  if (data.status !== 'DONE') {
    return (
      <View style={styles.center}>
        <Text style={styles.stateTitle}>{data.status === 'FAILED' ? '检测失败' : '检测中'}</Text>
        <Text style={styles.stateSub}>{data.status === 'FAILED' ? '推理服务暂时不可用，或文件无法解析出正文' : '通常 15–30 秒，下拉记录页刷新'}</Text>
      </View>
    );
  }

  const pass = data.aiRate != null && data.aiRate <= data.threshold;
  const body = data.paragraphs.filter((p) => !p.excluded);
  const high = body.filter((p) => (p.calibratedProb ?? 0) >= 0.7).length;
  const mid = body.filter((p) => { const v = p.calibratedProb ?? 0; return v >= 0.4 && v < 0.7; }).length;
  const low = body.length - high - mid;
  const n = Math.max(1, body.length);

  async function onShare() {
    setSharing(true);
    try {
      const s = await createShare(taskId, 7);
      await Share.share({ message: `知源检测报告（只读，7 天内有效）：${s.url}`, url: s.url });
    } catch (e) {
      Alert.alert('分享失败', e instanceof Error ? e.message : '请稍后重试');
    } finally { setSharing(false); }
  }
  function onPdf() { Linking.openURL(reportPdfUrl(taskId)).catch(() => Alert.alert('打开失败', '请稍后重试')); }
  function onCopyCred() {
    if (!data?.reportNo) return;
    Share.share({ message: `知源检测报告 编号 ${data.reportNo} 验证码 ${data.verifyCode}，验证：知源「验证报告」` }).catch(() => {});
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 16 }}>
      <View style={[styles.summaryCard, { backgroundColor: pass ? '#ecfdf5' : '#fef2f2' }]}>
        <Text style={styles.summaryTitle} numberOfLines={2}>{data.paperTitle}</Text>
        <Text style={[styles.summaryRate, { color: pass ? '#10b981' : '#ef4444' }]}>{data.aiRate?.toFixed(1)}%</Text>
        <Text style={styles.summaryVerdict}>{pass ? `低于红线 ${data.threshold}%，达标 ✓` : `超过红线 ${data.threshold}%，建议修改后重检`}</Text>
        <View style={styles.distBar}>
          <View style={{ flex: high / n, backgroundColor: '#ef4444' }} /><View style={{ flex: mid / n, backgroundColor: '#f59e0b' }} /><View style={{ flex: low / n, backgroundColor: '#10b981' }} />
        </View>
        <Text style={styles.distText}>高 {high} · 中 {mid} · 低 {low} · 正文 {body.length} 段</Text>
        {data.reportNo ? (
          <Pressable style={styles.cred} onPress={onCopyCred}>
            <Text style={styles.credText}>报告编号 <Text style={styles.credV}>{data.reportNo}</Text> · 验证码 <Text style={styles.credV}>{data.verifyCode}</Text></Text>
            <Text style={styles.credAct}>分享凭证</Text>
          </Pressable>
        ) : null}
      </View>

      <View style={styles.actions}>
        <Action label="问小白" onPress={() => router.push({ pathname: '/assistant/chat', params: { taskId: String(taskId) } })} primary />
        <Action label="下载 PDF" onPress={onPdf} />
        <Action label={sharing ? '生成中…' : '只读分享'} onPress={onShare} disabled={sharing} />
        <Action label="申诉" onPress={() => router.push({ pathname: '/feedback', params: { taskId: String(taskId) } })} />
      </View>

      <View style={styles.sourceCard}>
        <Text style={styles.sourceTitle}>疑似来源分布</Text>
        {Object.entries(data.sourceLabels || {}).sort(([, a], [, b]) => b - a).map(([label, ratio]) => (
          <View key={label} style={styles.sourceRow}>
            <Text style={styles.sourceLabel}>{SOURCE_LABEL[label] ?? label}</Text>
            <View style={styles.sourceBarTrack}><View style={[styles.sourceBarFill, { width: `${ratio * 100}%` }]} /></View>
            <Text style={styles.sourceRatio}>{(ratio * 100).toFixed(0)}%</Text>
          </View>
        ))}
      </View>

      <View style={styles.legend}>
        <Text style={styles.legendItem}><Text style={{ backgroundColor: '#fee2e2' }}>　</Text> 高疑似 AI</Text>
        <Text style={styles.legendItem}><Text style={{ backgroundColor: '#fef3c7' }}>　</Text> 中等疑似</Text>
        <Text style={styles.legendItem}>无底色 = 判定人写</Text>
      </View>

      {data.paragraphs.map((p) => <ParagraphCard key={p.paragraphIdx} paragraph={p} taskId={taskId} />)}
      <Text style={styles.foot}>模型 {data.modelVersion || '—'} · 置信度仅供参考，建议人工复核 · 最终以学校规定为准</Text>
    </ScrollView>
  );
}

function Action({ label, onPress, primary, disabled }: { label: string; onPress: () => void; primary?: boolean; disabled?: boolean }) {
  return (
    <Pressable style={[styles.action, primary && styles.actionPrimary, disabled && { opacity: 0.5 }]} onPress={onPress} disabled={disabled}>
      <Text style={[styles.actionText, primary && styles.actionTextPrimary]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  stateTitle: { fontSize: 18, fontWeight: '700', color: '#111827' }, stateSub: { fontSize: 13, color: '#6b7280', marginTop: 6, textAlign: 'center' },
  summaryCard: { borderRadius: 14, padding: 20, alignItems: 'center' },
  summaryTitle: { fontSize: 15, fontWeight: '600', color: '#111827', textAlign: 'center' },
  summaryRate: { fontSize: 44, fontWeight: '800', marginVertical: 6 },
  summaryVerdict: { fontSize: 13, color: '#374151' },
  distBar: { flexDirection: 'row', height: 8, borderRadius: 4, overflow: 'hidden', width: '100%', marginTop: 14, backgroundColor: '#e5e7eb' },
  distText: { fontSize: 11, color: '#6b7280', marginTop: 6 },
  cred: { marginTop: 12, backgroundColor: 'rgba(16,185,129,0.1)', borderRadius: 10, paddingVertical: 8, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', gap: 8, width: '100%' },
  credText: { flex: 1, fontSize: 12, color: '#374151' }, credV: { fontWeight: '700', color: '#047857' }, credAct: { fontSize: 12, color: '#0D9488', fontWeight: '600' },
  actions: { flexDirection: 'row', gap: 8, marginTop: 12 },
  action: { flex: 1, paddingVertical: 11, borderRadius: 10, backgroundColor: '#fff', alignItems: 'center', borderWidth: 1, borderColor: '#e5e7eb' },
  actionPrimary: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  actionText: { fontSize: 13, fontWeight: '600', color: '#111827' }, actionTextPrimary: { color: '#fff' },
  sourceCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 12 },
  sourceTitle: { fontSize: 14, fontWeight: '600', color: '#374151', marginBottom: 10 },
  sourceRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  sourceLabel: { width: 70, fontSize: 13, color: '#6b7280' },
  sourceBarTrack: { flex: 1, height: 8, backgroundColor: '#e5e7eb', borderRadius: 4, marginHorizontal: 8 },
  sourceBarFill: { height: 8, backgroundColor: '#0D9488', borderRadius: 4 },
  sourceRatio: { width: 40, fontSize: 12, color: '#374151', textAlign: 'right' },
  legend: { flexDirection: 'row', gap: 14, marginTop: 14, marginBottom: 6, paddingHorizontal: 4 },
  legendItem: { fontSize: 11, color: '#6b7280' },
  paragraphCard: { backgroundColor: '#fff', borderRadius: 12, padding: 16, marginTop: 10 },
  paragraphHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 8, gap: 8 },
  paragraphIdx: { fontSize: 12, color: '#9ca3af' },
  prob: { fontSize: 12, fontWeight: '600' },
  excluded: { fontSize: 11, color: '#6b7280', backgroundColor: '#f3f4f6', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 99 },
  paragraphText: { fontSize: 14, lineHeight: 24, color: '#111827' },
  askBtn: { marginTop: 10, alignSelf: 'flex-start' },
  askBtnText: { color: '#0D9488', fontSize: 13, fontWeight: '600' },
  foot: { textAlign: 'center', fontSize: 11, color: '#9ca3af', marginTop: 18 },
});
