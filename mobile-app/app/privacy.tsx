import { ScrollView, Text, StyleSheet, View } from 'react-native';

/** 隐私政策：文案与 web / uniapp 保持一致 */
const SECTIONS: Array<{ h: string; ps: string[] }> = [
  { h: '一、我们收集什么', ps: ['1. 账号信息：登录用的学号 / 工号及身份凭证，用于身份识别与登录鉴权。', '2. 检测内容：你提交检测的论文原文、段落切分结果及 AI 率判定结果，用于生成检测报告。', '3. 助手对话：你与「小白」检测助手的对话内容，用于回答你的问题。'] },
  { h: '二、我们怎么用', ps: ['1. 检测服务：对你提交的论文做 AI 生成内容判定，产出段落级 / 句子级 AI 率、疑似来源与解释。', '2. 服务改进：助手对话可能被人工抽样审阅以改进回答质量；审阅时你的身份信息会被脱敏处理。', '3. 我们不会将你的论文原文或对话内容用于广告投放，也不向第三方出售。'] },
  { h: '三、存储与保留', ps: ['1. 论文原文加密存储，30 天后自动删除。', '2. 检测报告保留 3 年，便于你随时回看与申诉举证。', '3. 助手对话记录保留 7 天，到期自动清理。', '4. 数据传输与存储均采用加密保护。'] },
  { h: '四、助手「小白」的边界', ps: ['小白是检测与解释助手：帮你理解报告、解释「为什么像 AI」、给出合规的原创修改方向，并协助整理申诉材料。', '小白不代写、不洗稿、不绕过检测。涉及代写、改写原文或编造申诉理由的请求，它会拒绝回答。'] },
  { h: '五、你的权利', ps: ['1. 查看与导出：你可随时查看并下载自己的检测报告。', '2. 申诉：对判定结果有异议，可通过「结果申诉」提交复核，平台人工处理。', '3. 删除：你可要求删除自己的账号与关联数据（法律要求保留的除外）。'] },
  { h: '六、联系我们', ps: ['如对本政策或你的个人信息有任何疑问，可通过「意见反馈」与我们联系。'] },
];

export default function PrivacyScreen() {
  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 20 }}>
      <Text style={styles.h1}>隐私政策</Text>
      <Text style={styles.updated}>更新日期：2026 年 10 月 · 生效日期：即日</Text>
      {SECTIONS.map((s) => (
        <View key={s.h} style={styles.sec}>
          <Text style={styles.h2}>{s.h}</Text>
          {s.ps.map((p, i) => <Text key={i} style={styles.p}>{p}</Text>)}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  h1: { fontSize: 24, fontWeight: '700', color: '#111827' },
  updated: { fontSize: 12, color: '#9ca3af', marginTop: 4, marginBottom: 12 },
  sec: { marginTop: 16 },
  h2: { fontSize: 15, fontWeight: '600', color: '#111827', marginBottom: 6 },
  p: { fontSize: 13, color: '#4b5563', lineHeight: 20, marginBottom: 6 },
});
