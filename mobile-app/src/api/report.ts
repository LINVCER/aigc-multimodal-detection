import { http, API_BASE, MOCK_MODE } from './client';

/** 报告 PDF 地址（后端 GET /api/v1/report/tasks/{id}/pdf 不校验登录，可直接用系统浏览器打开） */
export function reportPdfUrl(taskId: number): string {
  return `${API_BASE}/api/v1/report/tasks/${taskId}/pdf`;
}

export interface ReportShare {
  id: number;
  token: string;
  url: string;
  watermark: string | null;
  expiresAt: string;
  viewCount: number;
  revoked: boolean;
  expired: boolean;
  createdAt: string;
}

/** 生成只读分享链接 */
export async function createShare(taskId: number, expireDays = 7, watermark?: string): Promise<ReportShare> {
  if (MOCK_MODE) return { id: 1, token: 'mocktoken', url: 'https://example.com/s/mocktoken', watermark: watermark ?? null, expiresAt: '', viewCount: 0, revoked: false, expired: false, createdAt: '' };
  const resp = await http.post(`/api/v1/report/tasks/${taskId}/share`, { expireDays, watermark: watermark || undefined });
  return resp.data.data;
}

export interface ReportVerify {
  valid: boolean;
  signatureValid: boolean;
  message: string;
  reportNo?: string;
  paperTitle?: string;
  scenario?: string;
  threshold?: number;
  aiRate?: number | null;
  pass?: boolean;
  modelVersion?: string;
  wordCount?: number | null;
  bodyParagraphCount?: number | null;
  detectedAt?: string | null;
  signedAt?: string | null;
  fingerprint?: string | null;
  verifyCount?: number;
}

/** 公开验证报告真伪（不需登录） */
export async function verifyReport(reportNo: string, code: string): Promise<ReportVerify> {
  if (MOCK_MODE) return { valid: true, signatureValid: true, message: '离线 mock', reportNo, paperTitle: '示例论文', aiRate: 12.3, threshold: 20, pass: true, modelVersion: 'mock', fingerprint: 'MOCK', verifyCount: 1 };
  const resp = await http.post('/api/v1/verify', { reportNo, code });
  return resp.data.data;
}

/** 修改密码；成功后服务端作废当前 token */
export async function changePassword(oldPassword: string, newPassword: string, confirmPassword: string): Promise<void> {
  if (MOCK_MODE) return;
  await http.post('/api/v1/auth/password', { oldPassword, newPassword, confirmPassword });
}

export type FeedbackCategory = 'bug' | 'suggestion' | 'appeal';

/** 提交反馈 / 申诉 */
export async function submitFeedback(payload: { category: FeedbackCategory; content: string; taskId?: number; paragraphIdxs?: number[]; contact?: string }): Promise<{ id: number }> {
  if (MOCK_MODE) return { id: Date.now() };
  const resp = await http.post('/api/v1/feedback', payload);
  return resp.data.data;
}
