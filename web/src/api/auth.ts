import { http } from './client'
import type { LoginResp, UserInfo } from './types'

export async function login(username: string, password: string): Promise<LoginResp> {
  const resp = await http.post('/api/v1/auth/login', {
    username,
    password,
    clientId: 'e5cd7e4891bf95d1d19206ce24a7b32e',
    grantType: 'password',
    tenantId: '000000',
  })
  return resp.data.data
}

export async function logout(): Promise<void> {
  await http.post('/api/v1/auth/logout')
}

export async function me(): Promise<UserInfo> {
  const resp = await http.get('/api/v1/auth/me')
  return resp.data.data
}
