import { http } from './client'

/* =========== §3.1 Dashboard =========== */

export interface DashboardKpi {
  todayNewUser: number
  todayDetect: number
  totalUser: number
  totalDetect: number
  avgAiRate: number
}
export interface DashboardTrendRow {
  date: string
  newUser: number
  detect: number
  avgAiRate: number
}
export interface DashboardResp {
  kpi: DashboardKpi
  trend: DashboardTrendRow[]
  scenarioDist: Record<string, number>
  topUsers: Array<{ userId: number; userLabel: string; detectCount: number }>
  pendingFeedback: Array<any>
}

export async function getAdminDashboard(): Promise<DashboardResp> {
  const resp = await http.get('/admin/dashboard')
  return resp.data.data
}

/* =========== §3.2 用户列表 =========== */

export type LoginType = 'phone' | 'wechat' | 'email'
export type UserStatus = 'NORMAL' | 'BANNED' | 'INACTIVE' | 'SUSPICIOUS'

export interface AdminUser {
  id: number
  loginType: LoginType
  identity: string
  detectCount: number
  lastLoginAt: string
  registeredAt: string
  status: UserStatus
}

export async function listAdminUsers(params: {
  loginType?: LoginType | ''
  status?: UserStatus | ''
  keyword?: string
  minDetect?: number
  maxDetect?: number
  pageNum?: number
  pageSize?: number
} = {}): Promise<{ total: number; rows: AdminUser[] }> {
  const resp = await http.get('/admin/user/list', {
    params: { pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}

export async function banUser(id: number): Promise<void> {
  await http.post(`/admin/user/${id}/ban`)
}

export async function unbanUser(id: number): Promise<void> {
  await http.post(`/admin/user/${id}/unban`)
}

/* =========== §3.4 全平台任务列表 =========== */

export interface AdminTask {
  id: number
  paperTitle: string
  scenario: string
  threshold: number
  aiRate: number | null
  status: 'PENDING' | 'RUNNING' | 'DONE' | 'FAILED'
  createdAt: string
  wordCount: number | null
  modelVersion: string
  userId: number | null
  userLabel: string
}

export async function listAdminTasks(params: {
  status?: string
  scenario?: string
  userId?: number
  keyword?: string
  minAiRate?: number
  maxAiRate?: number
  pageNum?: number
  pageSize?: number
} = {}): Promise<{ total: number; rows: AdminTask[] }> {
  const resp = await http.get('/admin/task/list', {
    params: { pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}
