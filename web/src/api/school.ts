import { http } from './client'

/* ===================== 类型 ===================== */
export interface School {
  id: number
  name: string
  shortName?: string
  aliases?: string
  province?: string
  level?: string
  status?: string
}
export interface SchoolRule {
  degreeType: string
  college?: string
  aiRateLimit?: number
  plagiarismLimit?: number
  platform?: string
  effectiveYear?: number
  sourceUrl?: string
}
export interface SchoolDetail extends School {
  rules: SchoolRule[]
}
export interface ResolvedRule {
  resolved: boolean
  ruleId?: number
  schoolId?: number
  schoolName?: string
  degreeType?: string
  aiRateLimit?: number
  plagiarismLimit?: number
  platform?: string
  effectiveYear?: number
  sourceUrl?: string
  sourceType?: string
  label?: string
}
export interface RuleCandidate {
  id: number
  schoolId?: number
  schoolName?: string
  degreeType: string
  metric: string
  limitPct: number
  platform?: string
  effectiveYear?: number
  snippet?: string
  sourceUrl: string
  confidence: number
  status: string
}
export interface CrawlSeed {
  id: number
  schoolId?: number
  entryUrl: string
  adapter?: string
  enabled?: number
  lastCrawlAt?: string
  lastStatus?: string
  note?: string
}

/* ===================== C 端 ===================== */
export async function searchSchools(q?: string, province?: string, level?: string): Promise<School[]> {
  const resp = await http.get('/api/v1/schools', { params: { q, province, level } })
  return resp.data.data
}
export async function getSchoolDetail(id: number): Promise<SchoolDetail> {
  const resp = await http.get(`/api/v1/schools/${id}`)
  return resp.data.data
}
export async function setMySchool(schoolId: number | null, degreeType: string | null): Promise<void> {
  await http.put('/api/v1/me/school', { schoolId, degreeType })
}
export async function getMyRule(): Promise<ResolvedRule> {
  const resp = await http.get('/api/v1/me/rule')
  return resp.data.data
}

/* ===================== 后台 ===================== */
export async function adminListSchools(q?: string): Promise<School[]> {
  const resp = await http.get('/api/v1/admin/school/list', { params: { q } })
  return resp.data.data
}
export async function adminSaveSchool(dto: Partial<School>): Promise<void> {
  await http.post('/api/v1/admin/school/save', dto)
}
export async function adminSetSchoolStatus(id: number, status: string): Promise<void> {
  await http.post(`/api/v1/admin/school/${id}/status`, null, { params: { status } })
}
export async function adminImportSchools(list: Partial<School>[]): Promise<{ imported: number }> {
  const resp = await http.post('/api/v1/admin/school/import', list)
  return resp.data.data
}
export async function adminListSeeds(schoolId?: number): Promise<CrawlSeed[]> {
  const resp = await http.get('/api/v1/admin/school/seeds', { params: { schoolId } })
  return resp.data.data
}
export async function adminSaveSeed(dto: Partial<CrawlSeed>): Promise<void> {
  await http.post('/api/v1/admin/school/seeds/save', dto)
}
export async function adminRunSeed(id: number): Promise<{ job: string }> {
  const resp = await http.post(`/api/v1/admin/school/seeds/${id}/run`)
  return resp.data.data
}
export interface CandidatePage { total: number; rows: RuleCandidate[] }
export async function adminListCandidates(params: { status?: string; schoolId?: number; pageNum?: number; pageSize?: number } = {}): Promise<CandidatePage> {
  const resp = await http.get('/api/v1/admin/school/candidates', {
    params: { status: 'pending', pageNum: 1, pageSize: 20, ...params },
  })
  return resp.data.data
}
export interface CandidateMerge {
  schoolId: number
  college?: string
  degreeType: string
  aiRateLimit?: number
  plagiarismLimit?: number
  platform?: string
  effectiveYear?: number
  sourceUrl: string
}
export async function adminMergeCandidate(id: number, dto: CandidateMerge): Promise<{ ruleId: number }> {
  const resp = await http.post(`/api/v1/admin/school/candidates/${id}/merge`, dto)
  return resp.data.data
}
export async function adminRejectCandidate(id: number): Promise<void> {
  await http.post(`/api/v1/admin/school/candidates/${id}/reject`)
}
export async function adminSyncCandidates(): Promise<{ synced: number }> {
  const resp = await http.post('/api/v1/admin/school/candidates/sync')
  return resp.data.data
}
