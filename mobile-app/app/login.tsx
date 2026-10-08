import { useState, useEffect, useMemo } from 'react';
import { View, Text, TextInput, Pressable, Image, StyleSheet, ActivityIndicator, KeyboardAvoidingView, Platform, ScrollView } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import { useAuth } from '@/store/auth';
import { http, MOCK_MODE } from '@/api/client';

/**
 * 登录 / 注册页
 * 行内校验 · 密码可见切换 · 注册时密码强度与隐私协议勾选 · 记住账号 · 验证码点击刷新 · 服务端错误行内展示
 */
const REMEMBER_KEY = 'remember_username';
const USERNAME_RE = /^[A-Za-z0-9_.@-]{2,64}$/;
const STRENGTH_LABEL = ['', '弱', '一般', '较强', '强'];
const STRENGTH_COLOR = ['#e5e7eb', '#ef4444', '#f59e0b', '#0ea5e9', '#22c55e'];

export default function LoginScreen() {
  const { login, register, loading } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [remember, setRemember] = useState(true);
  const [agreed, setAgreed] = useState(false);
  const [captchaId, setCaptchaId] = useState('');
  const [captchaCode, setCaptchaCode] = useState('');
  const [captchaImg, setCaptchaImg] = useState('');
  const [captchaLoading, setCaptchaLoading] = useState(false);
  const [captchaFailed, setCaptchaFailed] = useState(false);
  const [serverError, setServerError] = useState('');
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  async function loadCaptcha() {
    if (MOCK_MODE) { setCaptchaId(''); setCaptchaImg(''); return; }
    setCaptchaLoading(true);
    setCaptchaFailed(false);
    try {
      const resp = await http.get('/api/v1/auth/captcha');
      setCaptchaId(resp.data.data.captchaId);
      setCaptchaImg(resp.data.data.imageBase64);
    } catch {
      setCaptchaId('');
      setCaptchaImg('');
      setCaptchaFailed(true);
    } finally {
      setCaptchaLoading(false);
      setCaptchaCode('');
    }
  }

  useEffect(() => {
    loadCaptcha();
    SecureStore.getItemAsync(REMEMBER_KEY).then((v) => { if (v) setUsername(v); }).catch(() => {});
  }, []);

  useEffect(() => {
    setServerError('');
    setTouched({});
    setConfirmPassword('');
  }, [mode]);

  const usernameError = useMemo(() => {
    if (!touched.username) return '';
    if (!username.trim()) return '请输入账号';
    if (mode === 'register' && !USERNAME_RE.test(username.trim())) return '只能包含字母、数字、_ . @ -，2-64 位';
    return '';
  }, [touched, username, mode]);
  const passwordError = useMemo(() => {
    if (!touched.password) return '';
    if (!password) return '请输入密码';
    if (mode === 'register') {
      if (password.length < 6 || password.length > 32) return '密码长度 6-32 位';
      if (!/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) return '需同时包含字母和数字';
      if (password.toLowerCase() === username.trim().toLowerCase()) return '密码不能与账号相同';
    }
    return '';
  }, [touched, password, username, mode]);
  const confirmError = useMemo(() => {
    if (mode !== 'register' || !touched.confirm) return '';
    if (!confirmPassword) return '请再次输入密码';
    if (confirmPassword !== password) return '两次输入的密码不一致';
    return '';
  }, [touched, confirmPassword, password, mode]);
  const captchaError = touched.captcha && captchaImg && !captchaCode.trim() ? '请输入验证码' : '';

  const strength = useMemo(() => {
    if (!password) return 0;
    let s = 0;
    if (password.length >= 8) s++;
    if (password.length >= 12) s++;
    if (/[A-Za-z]/.test(password) && /[0-9]/.test(password)) s++;
    if (/[^A-Za-z0-9]/.test(password)) s++;
    return Math.min(4, s);
  }, [password]);

  const canSubmit = !loading && !!username.trim() && !!password
    && (!captchaImg || !!captchaCode.trim())
    && (mode === 'login' || (!!confirmPassword && confirmPassword === password && agreed));

  const onSubmit = async () => {
    setTouched({ username: true, password: true, confirm: true, captcha: true });
    setServerError('');
    if (usernameError || passwordError || confirmError || captchaError) return;
    if (mode === 'register' && !agreed) { setServerError('请先阅读并同意《隐私政策》'); return; }
    const u = username.trim();
    try {
      if (mode === 'register') await register(u, password, confirmPassword, captchaId, captchaCode);
      else await login(u, password, captchaId, captchaCode);
      if (remember) await SecureStore.setItemAsync(REMEMBER_KEY, u);
      else await SecureStore.deleteItemAsync(REMEMBER_KEY);
    } catch (e) {
      setServerError(e instanceof Error ? e.message : (mode === 'register' ? '注册失败' : '登录失败'));
      loadCaptcha();
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Image source={require('../assets/icon.png')} style={styles.logo} />
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
          style={[styles.input, !!usernameError && styles.inputError]}
          placeholder="学号 / 工号 / 邮箱"
          autoCapitalize="none"
          autoCorrect={false}
          value={username}
          onChangeText={setUsername}
          onBlur={() => setTouched((t) => ({ ...t, username: true }))}
        />
        {!!usernameError && <Text style={styles.err}>{usernameError}</Text>}

        <View style={[styles.pwdRow, !!passwordError && styles.inputError]}>
          <TextInput
            style={styles.pwdInput}
            placeholder={mode === 'register' ? '设置密码（6-32 位，含字母和数字）' : '密码'}
            secureTextEntry={!showPwd}
            value={password}
            onChangeText={setPassword}
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
          />
          <Pressable onPress={() => setShowPwd((v) => !v)}><Text style={styles.eye}>{showPwd ? '隐藏' : '显示'}</Text></Pressable>
        </View>
        {!!passwordError && <Text style={styles.err}>{passwordError}</Text>}
        {mode === 'register' && !!password && (
          <View style={styles.strength}>
            {[1, 2, 3, 4].map((n) => <View key={n} style={[styles.bar, n <= strength && { backgroundColor: STRENGTH_COLOR[strength] }]} />)}
            <Text style={styles.strengthText}>{STRENGTH_LABEL[strength]}</Text>
          </View>
        )}

        {mode === 'register' && (
          <>
            <TextInput
              style={[styles.input, !!confirmError && styles.inputError]}
              placeholder="再次输入密码"
              secureTextEntry={!showPwd}
              value={confirmPassword}
              onChangeText={setConfirmPassword}
              onBlur={() => setTouched((t) => ({ ...t, confirm: true }))}
            />
            {!!confirmError && <Text style={styles.err}>{confirmError}</Text>}
          </>
        )}

        {!MOCK_MODE && (
          <View style={styles.captchaRow}>
            <TextInput
              style={[styles.input, styles.captchaInput, !!captchaError && styles.inputError]}
              placeholder="验证码"
              autoCapitalize="characters"
              maxLength={6}
              value={captchaCode}
              onChangeText={setCaptchaCode}
              onBlur={() => setTouched((t) => ({ ...t, captcha: true }))}
            />
            <Pressable style={styles.captchaBox} onPress={loadCaptcha} disabled={captchaLoading}>
              {captchaImg && !captchaLoading
                ? <Image source={{ uri: captchaImg }} style={styles.captchaImg} />
                : <Text style={styles.captchaHint}>{captchaLoading ? '加载中…' : captchaFailed ? '点击重试' : '获取验证码'}</Text>}
            </Pressable>
          </View>
        )}
        {!!captchaError && <Text style={styles.err}>{captchaError}</Text>}
        {!captchaError && captchaFailed && <Text style={styles.err}>验证码服务暂时不可用，点击右侧重试</Text>}

        <View style={styles.opts}>
          <Pressable style={styles.chk} onPress={() => setRemember((v) => !v)}>
            <View style={[styles.box, remember && styles.boxOn]}>{remember && <Text style={styles.tick}>✓</Text>}</View>
            <Text style={styles.chkText}>记住账号</Text>
          </Pressable>
          {mode === 'register' ? (
            <Pressable style={styles.chk} onPress={() => setAgreed((v) => !v)}>
              <View style={[styles.box, agreed && styles.boxOn]}>{agreed && <Text style={styles.tick}>✓</Text>}</View>
              <Text style={styles.chkText}>同意<Text style={styles.link}>《隐私政策》</Text></Text>
            </Pressable>
          ) : <Text style={styles.muted}>忘记密码请联系管理员</Text>}
        </View>

        {!!serverError && <View style={styles.serverError}><Text style={styles.serverErrorText}>{serverError}</Text></View>}

        <Pressable style={[styles.button, !canSubmit && styles.buttonDisabled]} onPress={onSubmit} disabled={!canSubmit}>
          {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>{mode === 'login' ? '登 录' : '注册并登录'}</Text>}
        </Pressable>

        <Text style={styles.hint} onPress={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? '还没有账号？立即注册' : '已有账号？去登录'}
        </Text>
        <Text style={styles.foot}>课题阶段免费 · 不代写、不改写 · 结果仅供参考</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 32, paddingVertical: 48, backgroundColor: '#fff' },
  logo: { width: 56, height: 56, borderRadius: 14, alignSelf: 'center', marginBottom: 12 },
  title: { fontSize: 28, fontWeight: '700', textAlign: 'center', color: '#0D9488' },
  subtitle: { fontSize: 13, textAlign: 'center', color: '#6b7280', marginTop: 8, marginBottom: 28 },
  seg: { flexDirection: 'row', backgroundColor: '#f3f4f6', borderRadius: 10, padding: 3, marginBottom: 18 },
  segBtn: { flex: 1, alignItems: 'center', paddingVertical: 8, borderRadius: 8 },
  segActive: { backgroundColor: '#fff', shadowColor: '#000', shadowOpacity: 0.06, shadowRadius: 3, elevation: 1 },
  segText: { color: '#6b7280', fontSize: 15 },
  segTextActive: { color: '#111827', fontSize: 15, fontWeight: '600' },
  input: { borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, marginBottom: 12 },
  inputError: { borderColor: '#ef4444' },
  pwdRow: { flexDirection: 'row', alignItems: 'center', borderWidth: 1, borderColor: '#d1d5db', borderRadius: 10, paddingRight: 12, marginBottom: 12 },
  pwdInput: { flex: 1, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16 },
  eye: { color: '#0D9488', fontSize: 13 },
  err: { color: '#ef4444', fontSize: 12, marginTop: -6, marginBottom: 10, marginLeft: 4 },
  strength: { flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: -4, marginBottom: 10 },
  bar: { width: 36, height: 4, borderRadius: 2, backgroundColor: '#e5e7eb' },
  strengthText: { fontSize: 12, color: '#6b7280', marginLeft: 6 },
  captchaRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 10 },
  captchaInput: { flex: 1 },
  captchaBox: { width: 108, height: 46, borderRadius: 10, borderWidth: 1, borderColor: '#e5e7eb', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  captchaImg: { width: '100%', height: '100%' },
  captchaHint: { fontSize: 12, color: '#0D9488' },
  opts: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 2, flexWrap: 'wrap', gap: 8 },
  chk: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  box: { width: 18, height: 18, borderRadius: 4, borderWidth: 1.5, borderColor: '#9ca3af', alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: '#0D9488', borderColor: '#0D9488' },
  tick: { color: '#fff', fontSize: 12, lineHeight: 14 },
  chkText: { fontSize: 13, color: '#6b7280' },
  link: { color: '#0D9488' },
  muted: { fontSize: 12, color: '#9ca3af' },
  serverError: { marginTop: 12, padding: 10, borderRadius: 10, backgroundColor: 'rgba(239,68,68,0.08)' },
  serverErrorText: { color: '#b91c1c', fontSize: 13, lineHeight: 18 },
  button: { backgroundColor: '#0D9488', borderRadius: 10, paddingVertical: 14, alignItems: 'center', marginTop: 16 },
  buttonDisabled: { opacity: 0.45 },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  hint: { fontSize: 13, color: '#0D9488', textAlign: 'center', marginTop: 20 },
  foot: { fontSize: 11, color: '#9ca3af', textAlign: 'center', marginTop: 10 },
});
