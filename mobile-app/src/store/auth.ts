import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { http, MOCK_MODE } from '@/api/client';

interface AuthState {
  token: string | null;
  username: string | null;
  loading: boolean;
  login: (username: string, password: string, captchaId?: string, captchaCode?: string) => Promise<void>;
  register: (username: string, password: string, confirmPassword: string, captchaId?: string, captchaCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
}

async function persist(token: string, username: string) {
  await SecureStore.setItemAsync('access_token', token);
  await SecureStore.setItemAsync('username', username);
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  username: null,
  loading: false,

  async login(username, password, captchaId, captchaCode) {
    set({ loading: true });
    try {
      let token: string;
      if (MOCK_MODE) {
        token = 'mock-token';
      } else {
        const resp = await http.post('/api/v1/auth/login', {
          username, password,
          ...(captchaId ? { captchaId, captchaCode } : {}),
        });
        token = resp.data.data.accessToken;
      }
      await persist(token, username);
      set({ token, username });
    } finally {
      set({ loading: false });
    }
  },

  async register(username, password, confirmPassword, captchaId, captchaCode) {
    set({ loading: true });
    try {
      let token: string;
      if (MOCK_MODE) {
        token = 'mock-token';
      } else {
        const resp = await http.post('/api/v1/auth/register', {
          username, password, confirmPassword,
          ...(captchaId ? { captchaId, captchaCode } : {}),
        });
        token = resp.data.data.accessToken;
      }
      await persist(token, username);
      set({ token, username });
    } finally {
      set({ loading: false });
    }
  },

  async logout() {
    await SecureStore.deleteItemAsync('access_token');
    await SecureStore.deleteItemAsync('username');
    set({ token: null, username: null });
  },

  async restore() {
    const token = await SecureStore.getItemAsync('access_token');
    const username = await SecureStore.getItemAsync('username');
    if (token) set({ token, username });
  },
}));
