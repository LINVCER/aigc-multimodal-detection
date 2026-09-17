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
