import { useState, useEffect } from 'react';
import { View, Text, TextInput, Pressable, Image, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useAuth } from '@/store/auth';
import { http, MOCK_MODE } from '@/api/client';

export default function LoginScreen() {
  const { login, register, loading } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [captchaId, setCaptchaId] = useState('');
  const [captchaCode, setCaptchaCode] = useState('');
  const [captchaImg, setCaptchaImg] = useState('');

  async function loadCaptcha() {
    if (MOCK_MODE) { setCaptchaId(''); setCaptchaImg(''); return; }
    try {
      const resp = await http.get('/api/v1/auth/captcha');
      setCaptchaId(resp.data.data.captchaId);
      setCaptchaImg(resp.data.data.imageBase64);
    } catch {
      setCaptchaId('');
      setCaptchaImg('');
    }
  }
  useEffect(() => { loadCaptcha(); }, []);

  const onSubmit = async () => {
    if (!username || !password) {
      Alert.alert('提示', '请输入账号和密码');
      return;
    }
    if (mode === 'register' && password !== confirmPassword) {
      Alert.alert('提示', '两次输入的密码不一致');
      return;
    }
    try {
      if (mode === 'register') {
        await register(username, password, confirmPassword, captchaId, captchaCode);
      } else {
        await login(username, password, captchaId, captchaCode);
      }
    } catch (e) {
      Alert.alert(mode === 'register' ? '注册失败' : '登录失败', e instanceof Error ? e.message : '请检查输入');
      if (captchaId) { loadCaptcha(); setCaptchaCode(''); }
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>知源</Text>
      <Text style={styles.subtitle}>看得懂的论文 AI 率检测 · 溯源 · 不代写</Text>

      <View style={styles.seg}>
        <Pressable style={[styles.segBtn, mode === 'login' && styles.segActive]} onPress={() => setMode('login')}>
          <Text style={mode === 'login' ? styles.segTextActive : styles.segText}>登录</Text>
        </Pressable>
        <Pressable style={[styles.segBtn, mode === 'register' && styles.segActive]} onPress={() => setMode('register')}>
          <Text style={mode === 'register' ? styles.segTextActive : styles.segText}>注册</Text>
        </Pressable>
      </View>

      <TextInput
        style={styles.input}
        placeholder="学号 / 工号 / 邮箱"
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
      />
      <TextInput
        style={styles.input}
        placeholder="密码（6-32 位）"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      {mode === 'register' && (
        <TextInput
          style={styles.input}
          placeholder="再次输入密码"
          secureTextEntry
          value={confirmPassword}
          onChangeText={setConfirmPassword}
        />
      )}

      <View style={styles.captchaRow}>
        <TextInput
          style={[styles.input, styles.captchaInput]}
          placeholder="验证码"
          autoCapitalize="characters"
          value={captchaCode}
          onChangeText={setCaptchaCode}
        />
        {captchaImg ? (
          <Pressable onPress={loadCaptcha}>
            <Image source={{ uri: captchaImg }} style={styles.captchaImg} />
          </Pressable>
        ) : null}
      </View>

      <Pressable style={styles.button} onPress={onSubmit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>{mode === 'login' ? '登 录' : '注册并登录'}</Text>}
      </Pressable>

      <Text style={styles.hint} onPress={() => setMode(mode === 'login' ? 'register' : 'login')}>
        {mode === 'login' ? '还没有账号？立即注册' : '已有账号？去登录'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', paddingHorizontal: 32, backgroundColor: '#fff' },
  title: { fontSize: 28, fontWeight: '700', textAlign: 'center', color: '#0D9488' },
  subtitle: { fontSize: 13, textAlign: 'center', color: '#6b7280', marginTop: 8, marginBottom: 28 },
  seg: { flexDirection: 'row', backgroundColor: '#f3f4f6', borderRadius: 10, padding: 3, marginBottom: 18 },
  segBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8 },
  segActive: { backgroundColor: '#fff', shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 3, elevation: 1 },
  segText: { color: '#6b7280', fontSize: 15 },
  segTextActive: { color: '#111827', fontSize: 15, fontWeight: '600' },
  input: {
    borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, marginBottom: 14,
  },
  captchaRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  captchaInput: { flex: 1 },
  captchaImg: { width: 108, height: 46, borderRadius: 10, marginBottom: 14 },
  button: {
    backgroundColor: '#0D9488', borderRadius: 10, paddingVertical: 14,
    alignItems: 'center', marginTop: 6,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  hint: { fontSize: 13, color: '#0D9488', textAlign: 'center', marginTop: 20 },
});
