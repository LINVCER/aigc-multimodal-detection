import { View, Text, Pressable, StyleSheet } from 'react-native';
import { useAuth } from '@/store/auth';

export default function ProfileScreen() {
  const { username, logout } = useAuth();

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.avatar}>👤</Text>
        <Text style={styles.name}>{username ?? '已登录用户'}</Text>
      </View>

      <View style={styles.menu}>
        <Text style={styles.menuItem}>额度余额（接入后端后展示）</Text>
        <Text style={styles.menuItem}>历史报告下载</Text>
        <Text style={styles.menuItem}>关于与隐私政策</Text>
      </View>

      <Pressable style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>退出登录</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6', padding: 20 },
  card: {
    backgroundColor: '#fff', borderRadius: 12, padding: 24, alignItems: 'center',
  },
  avatar: { fontSize: 48 },
  name: { fontSize: 18, fontWeight: '600', marginTop: 8, color: '#111827' },
  menu: { backgroundColor: '#fff', borderRadius: 12, marginTop: 16 },
  menuItem: {
    fontSize: 15, color: '#374151', paddingVertical: 16, paddingHorizontal: 18,
    borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: '#e5e7eb',
  },
  logoutBtn: {
    backgroundColor: '#fff', borderRadius: 12, paddingVertical: 14,
    alignItems: 'center', marginTop: 16,
  },
  logoutText: { color: '#ef4444', fontSize: 15, fontWeight: '600' },
});
