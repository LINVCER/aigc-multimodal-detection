import { useState } from 'react';
import { View, Text, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { useRouter } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { uploadPaper } from '@/api/detect';

const DEGREES = [
  { key: 'BACHELOR', label: '本科', threshold: 20 },
  { key: 'MASTER', label: '硕士', threshold: 15 },
  { key: 'PHD', label: '博士', threshold: 10 },
] as const;

export default function UploadScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [degree, setDegree] = useState<string>('BACHELOR');
  const [file, setFile] = useState<{ uri: string; name: string; mimeType?: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const pickFile = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
      ],
      copyToCacheDirectory: true,
    });
    if (!result.canceled && result.assets[0]) {
      const asset = result.assets[0];
      if (asset.size && asset.size > 20 * 1024 * 1024) {
        Alert.alert('提示', '文件不能超过 20MB');
        return;
      }
      setFile({ uri: asset.uri, name: asset.name, mimeType: asset.mimeType });
    }
  };

  const submit = async () => {
    if (!file) {
      Alert.alert('提示', '请先选择论文文件');
      return;
    }
    setSubmitting(true);
    try {
      await uploadPaper(file, degree);
      await queryClient.invalidateQueries({ queryKey: ['tasks'] });
      Alert.alert('提交成功', '检测任务已创建，请在「检测记录」查看进度', [
        { text: '查看', onPress: () => router.push('/') },
      ]);
      setFile(null);
    } catch (e) {
      Alert.alert('提交失败', e instanceof Error ? e.message : '请稍后重试');
    } finally {
      setSubmitting(false);
    }
  };

  const currentThreshold = DEGREES.find((d) => d.key === degree)?.threshold;

  return (
    <View style={styles.container}>
      <Text style={styles.sectionTitle}>学位类型</Text>
      <View style={styles.degreeRow}>
        {DEGREES.map((d) => (
          <Pressable
            key={d.key}
            style={[styles.degreeChip, degree === d.key && styles.degreeChipActive]}
            onPress={() => setDegree(d.key)}
          >
            <Text style={[styles.degreeText, degree === d.key && styles.degreeTextActive]}>
              {d.label}
            </Text>
          </Pressable>
        ))}
      </View>
      <Text style={styles.thresholdHint}>教育部红线：AI 率 ≤ {currentThreshold}%</Text>

      <Text style={styles.sectionTitle}>论文文件</Text>
      <Pressable style={styles.fileBox} onPress={pickFile}>
        <Text style={styles.fileBoxIcon}>{file ? '📄' : '📎'}</Text>
        <Text style={styles.fileBoxText} numberOfLines={1}>
          {file ? file.name : '点击选择 PDF / Word / TXT（≤ 20MB）'}
        </Text>
      </Pressable>

      <Pressable style={[styles.submitBtn, (!file || submitting) && styles.submitBtnDisabled]} onPress={submit} disabled={!file || submitting}>
        {submitting ? <ActivityIndicator color="#fff" /> : <Text style={styles.submitText}>提交检测</Text>}
      </Pressable>

      <Text style={styles.privacyHint}>
        论文原文加密存储，30 天后自动删除；检测报告保留 3 年
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff', padding: 20 },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: '#374151', marginTop: 20, marginBottom: 10 },
  degreeRow: { flexDirection: 'row', gap: 10 },
  degreeChip: {
    paddingHorizontal: 20, paddingVertical: 10, borderRadius: 20,
    borderWidth: 1, borderColor: '#d1d5db',
  },
  degreeChipActive: { backgroundColor: '#1a56db', borderColor: '#1a56db' },
  degreeText: { fontSize: 14, color: '#374151' },
  degreeTextActive: { color: '#fff', fontWeight: '600' },
  thresholdHint: { fontSize: 12, color: '#f59e0b', marginTop: 8 },
  fileBox: {
    borderWidth: 1.5, borderColor: '#d1d5db', borderStyle: 'dashed', borderRadius: 12,
    paddingVertical: 36, alignItems: 'center', backgroundColor: '#f9fafb',
  },
  fileBoxIcon: { fontSize: 32, marginBottom: 8 },
  fileBoxText: { fontSize: 13, color: '#6b7280', paddingHorizontal: 20 },
  submitBtn: {
    backgroundColor: '#1a56db', borderRadius: 10, paddingVertical: 14,
    alignItems: 'center', marginTop: 28,
  },
  submitBtnDisabled: { opacity: 0.4 },
  submitText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  privacyHint: { fontSize: 11, color: '#9ca3af', textAlign: 'center', marginTop: 16 },
});
