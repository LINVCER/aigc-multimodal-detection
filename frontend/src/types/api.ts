// API 响应类型定义

// ===== 基础类型 =====
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

// ===== 用户相关 =====
export interface User {
  id: string
  username: string
  role: 'teacher' | 'journalist' | 'admin'
  created_at: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

// ===== 检测结果 =====
export interface DetectionResult {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  is_ai_generated: boolean
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
  model_attribution?: Record<string, number>
  raw_scores?: Record<string, number>
  created_at: string
  completed_at?: string
}

// ===== 文本检测 =====
export interface TextDetectionResult extends DetectionResult {
  text: string
  chunks?: TextChunk[]
  model_info?: ModelInfo
}

export interface TextChunk {
  text: string
  confidence: number
  is_ai: boolean
}

export interface ModelInfo {
  base_model: string
  checkpoint: string
  val_acc?: number
  val_f1?: number
}

// ===== 图像检测 =====
export interface ImageDetectionResult extends DetectionResult {
  image_url: string
  frequency_analysis?: FrequencyAnalysis
}

export interface FrequencyAnalysis {
  high_freq_energy: number
  spectral_entropy: number
}

// ===== 音频检测 =====
export interface AudioDetectionResult extends DetectionResult {
  audio_url: string
  branch_scores?: BranchScore[]
}

export interface BranchScore {
  name: string
  score: number
  status: string
}

// ===== 论文检测 =====
export interface ThesisDetectionResult extends DetectionResult {
  title: string
  chapters: ThesisChapter[]
  style_consistency: number
  style_variance: number
  ai_ratio: number
  forensics?: ForensicsReport
  suggestions?: string[]
}

export interface ThesisChapter {
  title: string
  content: string
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
  reasons?: string[]
}

export interface ForensicsReport {
  citation_check?: CitationCheck
  data_specificity?: DataSpecificity
  overall_risk: number
}

export interface CitationCheck {
  total_citations: number
  suspicious_count: number
  details: CitationDetail[]
}

export interface CitationDetail {
  citation: string
  suspicion: number
  reason: string
}

export interface DataSpecificity {
  score: number
  level: 'high' | 'medium' | 'low'
  details: string[]
}

// ===== 批量检测 =====
export interface BatchDetectionResult {
  batch_id: string
  status: 'pending' | 'processing' | 'completed' | 'cancelled' | 'partial'
  total: number
  completed: number
  results: BatchItemResult[]
  created_at: string
  finished_at?: string
}

export interface BatchItemResult {
  filename: string
  status: 'success' | 'failed'
  result?: DetectionResult
  error?: string
}

// ===== 鲁棒性测试 =====
export interface RobustnessTestResult {
  original_score: number
  attacks: AttackResult[]
  overall_verdict: string
  vulnerability_score: number
}

export interface AttackResult {
  attack_type: string
  description: string
  score_after: number
  delta: number
  vulnerable: boolean
}

// ===== 报告 =====
export interface ExplanationReport {
  task_id: string
  summary: string
  confidence_explanation: string
  feature_analysis: FeatureAnalysis[]
  recommendations: string[]
}

export interface FeatureAnalysis {
  feature: string
  value: number
  description: string
  impact: 'positive' | 'negative' | 'neutral'
}

// ===== 管理后台 =====
export interface AdminStats {
  total_users: number
  total_detections: number
  detections_today: number
  avg_confidence: number
  detection_trend: TrendItem[]
}

export interface TrendItem {
  date: string
  count: number
}

export interface DetectionRecord {
  id: string
  user_id: string
  username: string
  type: 'text' | 'image' | 'audio' | 'thesis'
  confidence: number
  risk_level: 'low' | 'medium' | 'high'
  created_at: string
}

// ===== 降AIGC =====
export interface ReduceAIGCResult {
  original_score: number
  optimized_score: number
  reduction_rate: number
  optimized_text: string
  changes: TextChange[]
}

export interface TextChange {
  type: 'synonym' | 'restructure' | 'remove_slop' | 'paraphrase'
  original: string
  optimized: string
  position: number
}

// ===== 篡改检测 =====
export interface TamperingDetectionResult {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  is_tampered: boolean
  tampering_score: number
  tampering_type: string
  risk_level: 'low' | 'medium' | 'high'
  mask_image: string
  overlay_image: string
  branches: TamperingBranchResult[]
  created_at: string
}

export interface TamperingBranchResult {
  name: string
  confidence: number
  is_tampered: boolean
}
