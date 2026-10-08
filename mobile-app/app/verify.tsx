import { useEffect, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, ScrollView, ActivityIndicator } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { verifyReport, type ReportVerify } from '@/api/report';

/** 验证报告真伪：手动输入编号 + 验证码；带 reportNo/code 参数进来时自动验证 */
const SCENARIO_LABEL: Record<string, string> = { academic_bachelor: '本科论文', academic_master: '硕士论文', academic_phd: '博士论文', job_report: '职业报告', self_media: '自媒体', other: '其他' };
const fmt = (s?: string | null) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—');

export default function VerifyScreen() {
  const params = useLocalSearchParams<{ reportNo?: string; code?: string }>();
  const [reportNo, setReportNo] = useState((params.reportNo || '').toUpperCase());
  const [code, setCode] = useState((params.code || '').toUpperCase());
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReportVerify | null>(null);
  const [error, setError] = useState('');

  async function doVerify() {
    setError(''); setResult(null);
    const no = reportNo.trim().toUpperCase().replace(/\s+/g, '');
    const c = code.trim().toUpperCase();
    if (!no || !c) { setError('请输入报告编号和验证码'); return; }
    setLoading(true);
    try { setResult(await verifyReport(no, c)); }
    catch (e) { setError(e instanceof Error ? e.message : '验证失败，请稍后再试'); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (reportNo && code) doVerify(); }, []);

  const tone = result ? (result.valid ? (result.signatureValid ? 'ok' : 'warn') : 'bad') : '';
  const toneColor = tone === 'ok' ? '#10b981' : tone === 'warn' ? '#f59e0b' : '#ef4444';

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 20 }} keyboardShouldPersistTaps="handled">
      <Text style={styles.h1}>验证检测报告</Text>
      <Text style={styles.p}>每份知源报告完成时都签发唯一编号、验证码和服务端签名。输入 PDF 封面上的编号与验证码，核对报告是否由知源签发、内容是否被改动。</Text>

      <View style={styles.card}>
        <Text style={styles.label}>报告编号</Text>
        <TextInput style={styles.input} placeholder="ZY-20261008-XXXXXX" autoCapitalize="characters" value={reportNo} onChangeText={(v) => setReportNo(v.toUpperCase())} />
        <Text style={styles.label}>验证码</Text>
        <TextInput style={styles.input} placeholder="PDF 封面 8 位验证码" autoCapitalize="characters" maxLength={8} value={code} onChangeText={(v) => setCode(v.toUpperCase())} />
        {!!error && <Text style={styles.err}>{error}</Text>}
        <Pressable style={[styles.btn, loading && { opacity: 0.6 }]} onPress={doVerify} disabled={loading}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>验 证</Text>}
        </Pressable>
      </View>

      {result && (
        <View style={[styles.card, { borderWidth: 1, borderColor: toneColor }]}>
          <View style={styles.resultHead}>
            <View style={[styles.shield, { backgroundColor: toneColor }]}><Text style={styles.shieldText}>{tone === 'ok' ? '✓' : tone === 'warn' ? '!' : '✕'}</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.resultTitle}>{tone === 'ok' ? '报告真实有效' : tone === 'warn' ? '编号有效，但内容已变动' : '验证未通过'}</Text>
              <Text style={styles.resultSub}>{result.message}</Text>
            </View>
          </View>
          {result.valid && (
            <View style={styles.kv}>
              <Row k="报告编号" v={result.reportNo || '—'} />
              <Row k="论文标题" v={result.paperTitle || '—'} />
              <Row k="检测结论" v={`${Number(result.aiRate).toFixed(1)}% · 红线 ${result.threshold}% · ${result.pass ? '达标' : '超线'} · ${SCENARIO_LABEL[result.scenario || ''] || result.scenario || ''}`} color={result.pass ? '#10b981' : '#ef4444'} />
              <Row k="检测时间" v={fmt(result.detectedAt)} />
              <Row k="模型" v={`${result.modelVersion || '—'} · ${result.wordCount || '—'} 字`} />
              <Row k="签名指纹" v={result.fingerprint || '—'} />
              <Row k="被验证" v={`${result.verifyCount} 次`} />
              {!result.signatureValid && <Text style={styles.warnNote}>签名重算与签发时不一致：报告完成后结果被修改过，或服务端密钥已更换。请以知源平台内的在线报告为准。</Text>}
            </View>
          )}
        </View>
      )}

      <Text style={styles.howTitle}>怎么核对</Text>
      <Text style={styles.how}>1. 编号与验证码印在 PDF 封面「报告溯源凭证」区域，也可在知源结果页复制。</Text>
      <Text style={styles.how}>2. 验证页显示的「签名指纹」应与 PDF 上一致；不一致说明 PDF 被改过。</Text>
      <Text style={styles.how}>3. 验证通过只说明报告由知源签发且内容未变，检测结论本身仍以学校规定为准。</Text>
    </ScrollView>
  );
}

function Row({ k, v, color }: { k: string; v: string; color?: string }) {
  return (
    <View style={styles.row}><Text style={styles.k}>{k}</Text><Text style={[styles.v, color ? { color, fontWeight: '700' } : null]}>{v}</Text></View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  h1: { fontSize: 24, fontWeight: '700', color: '#111827' },
  p: { fontSize: 13, color: '#6b7280', lineHeight: 20, marginTop: 6, marginBottom: 16 },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 18, marginBottom: 16 },
  label: { fontSize: 12, color: '#6b7280', marginBottom: 6, marginTop: 6 },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, letterSpacing: 0.5 },
  err: { color: '#ef4444', fontSize: 12, marginTop: 8 },
  btn: { marginTop: 16, backgroundColor: '#0D9488', borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  resultHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  shield: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  shieldText: { color: '#fff', fontSize: 20, fontWeight: '700' },
  resultTitle: { fontSize: 16, fontWeight: '700', color: '#111827' },
  resultSub: { fontSize: 12, color: '#6b7280', marginTop: 2 },
  kv: { marginTop: 14, paddingTop: 12, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#e5e7eb' },
  row: { flexDirection: 'row', paddingVertical: 5 },
  k: { width: 72, fontSize: 13, color: '#6b7280' },
  v: { flex: 1, fontSize: 13, color: '#111827' },
  warnNote: { marginTop: 10, backgroundColor: '#fef3c7', color: '#92400e', borderRadius: 8, padding: 10, fontSize: 12, lineHeight: 18 },
  howTitle: { fontSize: 14, fontWeight: '600', color: '#111827', marginTop: 8, marginBottom: 6 },
  how: { fontSize: 12, color: '#6b7280', lineHeight: 18, marginBottom: 4 },
});
