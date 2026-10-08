import { useEffect } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuth } from '@/store/auth';

const queryClient = new QueryClient();

function AuthGate() {
  const { token, restore } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    restore();
  }, []);

  useEffect(() => {
    const inLogin = segments[0] === 'login';
    if (!token && !inLogin) {
      router.replace('/login');
    } else if (token && inLogin) {
      router.replace('/');
    }
  }, [token, segments]);

  return (
    <Stack screenOptions={{ headerTitleAlign: 'center' }}>
      <Stack.Screen name="login" options={{ headerShown: false }} />
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="task/[id]" options={{ title: '检测报告' }} />
      <Stack.Screen name="assistant/chat" options={{ title: '小白', headerShown: true }} />
      <Stack.Screen name="verify" options={{ title: '验证报告' }} />
      <Stack.Screen name="feedback" options={{ title: '意见反馈' }} />
      <Stack.Screen name="privacy" options={{ title: '隐私政策' }} />
      <Stack.Screen name="account/password" options={{ title: '修改密码' }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthGate />
    </QueryClientProvider>
  );
}
