import { useMemo, useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { changePassword } from '@/api/report';
import { useAuth } from '@/store/auth';

/** 修改密码：规则与 web / uniapp 一致（6-32 位，含字母和数字）；成功后服务端作废 token，回到登录页 */
export default function PasswordScreen() {
  const router = useRouter();
  const { logout } = useAuth();
  const [oldPwd, setOldPwd] = useState('');
  const [newPwd, setNewPwd] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);

  const error = useMemo(() => {
    if (!oldPwd) return '请输入原密码';
    if (newPwd.length < 6 || newPwd.length > 32) return '新密码长度 6-32 位';
    if (!/[A-Za-z]/.test(newPwd) || !/[0-9]/.test(newPwd)) return '新密码需同时包含字母和数字';
    if (newPwd === oldPwd) return '新密码不能与原密码相同';
    if (confirm !== newPwd) return '两次输入的新密码不一致';
    return '';
  }, [oldPwd, newPwd, confirm]);

  async function submit() {
    if (error) { Alert.alert('提示', error); return; }
    setLoading(true);
    try {
      await changePassword(oldPwd, newPwd, confirm);
      Alert.alert('密码已修改', '请用新密码重新登录', [{ text: '好', onPress: async () => { await logout(); router.replace('/login'); } }]);
    } catch (e) {
      Alert.alert('修改失败', e instanceof Error ? e.message : '请稍后重试');
    } finally { setLoading(false); }
  }

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.label}>原密码</Text>
        <TextInput style={styles.input} secureTextEntry value={oldPwd} onChangeText={setOldPwd} placeholder="原密码" />
        <Text style={styles.label}>新密码</Text>
        <TextInput style={styles.input} secureTextEntry value={newPwd} onChangeText={setNewPwd} placeholder="6-32 位，含字母和数字" />
        <Text style={styles.label}>确认新密码</Text>
        <TextInput style={styles.input} secureTextEntry value={confirm} onChangeText={setConfirm} placeholder="再次输入新密码" />
        <Text style={styles.hint}>{(oldPwd || newPwd) && error ? error : '修改成功后所有设备需重新登录'}</Text>
        <Pressable style={[styles.btn, (!!error || loading) && { opacity: 0.45 }]} disabled={!!error || loading} onPress={submit}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.btnText}>确认修改</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f3f4f6', padding: 20 },
  card: { backgroundColor: '#fff', borderRadius: 14, padding: 18 },
  label: { fontSize: 12, color: '#6b7280', marginBottom: 6, marginTop: 8 },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  hint: { fontSize: 12, color: '#9ca3af', marginTop: 10 },
  btn: { marginTop: 16, backgroundColor: '#0D9488', borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  btnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
