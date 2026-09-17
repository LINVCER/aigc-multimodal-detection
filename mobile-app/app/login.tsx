import { useState } from 'react';
import { View, Text, TextInput, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useAuth } from '@/store/auth';

export default function LoginScreen() {
  const { login, loading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const onSubmit = async () => {
    if (!username || !password) {
      Alert.alert('提示', '请输入账号和密码');
      return;
    }
    try {
      await login(username, password);
    } catch (e) {
      Alert.alert('登录失败', e instanceof Error ? e.message : '请检查账号密码');
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>论文 AIGC 检测</Text>
      <Text style={styles.subtitle}>教育部 2026 新规 · 学位论文 AI 率检测</Text>

      <TextInput
        style={styles.input}
        placeholder="学号 / 工号"
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
      />
      <TextInput
        style={styles.input}
        placeholder="密码"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      <Pressable style={styles.button} onPress={onSubmit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>登 录</Text>}
      </Pressable>

      <Text style={styles.hint}>首次使用请通过学校统一身份认证或联系管理员开通</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', paddingHorizontal: 32, backgroundColor: '#fff' },
  title: { fontSize: 28, fontWeight: '700', textAlign: 'center', color: '#1a56db' },
  subtitle: { fontSize: 13, textAlign: 'center', color: '#6b7280', marginTop: 8, marginBottom: 40 },
  input: {
    borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, marginBottom: 14,
  },
  button: {
    backgroundColor: '#1a56db', borderRadius: 10, paddingVertical: 14,
    alignItems: 'center', marginTop: 6,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  hint: { fontSize: 12, color: '#9ca3af', textAlign: 'center', marginTop: 24 },
});
