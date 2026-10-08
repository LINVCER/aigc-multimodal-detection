import { View, Text, Pressable, StyleSheet, Alert, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { useAuth } from '@/store/auth';

/** 我的：与 web / uniapp 同一套入口 —— 修改密码 · 验证报告真伪 · 意见反馈 · 隐私政策 · 退出 */
export default function ProfileScreen() {
  const router = useRouter();
  const { username, logout } = useAuth();
  const initial = (username || 'U').charAt(0).toUpperCase();

  function onLogout() {
    Alert.alert('退出登录', '确定要退出吗？', [
      { text: '取消', style: 'cancel' },
      { text: '退出', style: 'destructive', onPress: async () => { await logout(); router.replace('/login'); } },
    ]);
  }

  const GROUPS: Array<{ title: string; rows: Array<{ label: string; sub?: string; to: string }> }> = [
    { title: '账户', rows: [
      { label: '历史报告', sub: '查看与下载', to: '/' },
      { label: '修改密码', to: '/account/password' },
    ] },
    { title: '报告', rows: [
      { label: '验证报告真伪', sub: '输入编号与验证码', to: '/verify' },
    ] },
    { title: '关于', rows: [
      { label: '意见反馈', to: '/feedback' },
      { label: '隐私政策', to: '/privacy' },
    ] },
  ];

  return (
    <ScrollView style={styles.container} contentContainerStyle={{ padding: 20 }}>
      <View style={styles.card}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{initial}</Text></View>
        <View>
          <Text style={styles.name}>{username ?? '已登录用户'}</Text>
          <Text style={styles.role}>知源个人版 · 课题阶段免费</Text>
        </View>
      </View>

      {GROUPS.map((g) => (
        <View key={g.title}>
          <Text style={styles.groupLabel}>{g.title}</Text>
          <View style={styles.menu}>
            {g.rows.map((r, i) => (
              <Pressable key={r.label} style={[styles.row, i < g.rows.length - 1 && styles.rowBorder]} onPress={() => router.push(r.to as any)}>
                <Text style={styles.rowLabel}>{r.label}</Text>
                <View style={styles.rowRight}>{r.sub ? <Text style={styles.rowSub}>{r.sub}</Text> : null}<Text style={styles.chevron}>›</Text></View>
              </Pressable>
            ))}
          </View>
        </View>
      ))}

      <Pressable style={styles.logoutBtn} onPress={onLogout}>
        <Text style={styles.logoutText}>退出登录</Text>
      </Pressable>
      <Text style={styles.version}>知源 · 不代写、不改写 · 结果仅供参考</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6' },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 18, flexDirection: 'row', alignItems: 'center', gap: 14 },
  avatar: { width: 56, height: 56, borderRadius: 28, backgroundColor: '#0D9488', alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: '#fff', fontSize: 24, fontWeight: '700' },
  name: { fontSize: 18, fontWeight: '600', color: '#111827' },
  role: { fontSize: 12, color: '#6b7280', marginTop: 4 },
  groupLabel: { fontSize: 12, color: '#6b7280', marginTop: 20, marginBottom: 6, marginLeft: 6, textTransform: 'uppercase' },
  menu: { backgroundColor: '#fff', borderRadius: 14, overflow: 'hidden' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 15, paddingHorizontal: 18 },
  rowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#e5e7eb' },
  rowLabel: { fontSize: 15, color: '#111827' },
  rowRight: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  rowSub: { fontSize: 12, color: '#9ca3af' },
  chevron: { fontSize: 20, color: '#c7c7cc', lineHeight: 20 },
  logoutBtn: { backgroundColor: '#fff', borderRadius: 14, paddingVertical: 14, alignItems: 'center', marginTop: 24 },
  logoutText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
  version: { textAlign: 'center', fontSize: 11, color: '#9ca3af', marginTop: 14 },
});
