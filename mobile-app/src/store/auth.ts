import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import { http, MOCK_MODE } from '@/api/client';

interface AuthState {
  token: string | null;
  username: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  token: null,
  username: null,
  loading: false,

  async login(username, password) {
    set({ loading: true });
    try {
      let token: string;
      if (MOCK_MODE) {
        token = 'mock-token';
      } else {
        const resp = await http.post('/api/v1/auth/login', { username, password });
        token = resp.data.data.accessToken;
      }
      await SecureStore.setItemAsync('access_token', token);
      set({ token, username });
    } finally {
      set({ loading: false });
    }
  },

  async logout() {
    await SecureStore.deleteItemAsync('access_token');
    set({ token: null, username: null });
  },

  async restore() {
    const token = await SecureStore.getItemAsync('access_token');
    if (token) set({ token });
  },
}));
