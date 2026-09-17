import axios from 'axios';
import * as SecureStore from 'expo-secure-store';

// EXPO_PUBLIC_API_BASE 为空时启用 mock（离线开发 UI 用）
export const API_BASE = process.env.EXPO_PUBLIC_API_BASE ?? '';
export const MOCK_MODE = !API_BASE;

export const http = axios.create({
  baseURL: API_BASE || 'http://mock.local',
  timeout: 30_000,
});

http.interceptors.request.use(async (config) => {
  const token = await SecureStore.getItemAsync('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (resp) => {
    // 后端统一响应体 { code, msg, data }，code=0 为成功（若依 R 结构 code=200）
    const body = resp.data;
    if (body && typeof body.code === 'number' && body.code !== 0 && body.code !== 200) {
      return Promise.reject(new Error(body.msg ?? '请求失败'));
    }
    return resp;
  },
  (err) => {
    if (err.response?.status === 401) {
      // token 失效交由 auth store 处理跳登录
    }
    return Promise.reject(err);
  },
);
