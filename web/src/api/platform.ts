import { http } from './client'

/* ===================== 平台参数配置（推理服务透传） ===================== */

export interface PlatformTextConfig {
  backend: string
  load_error: string | null
  detail: {
    model_version: string
    device: string
    checkpoint_path: string
    backbone?: string
  } | null
  modelsDir: string
  checkpoints: string[]
}

export interface PlatformAssistantConfig {
  enabled: boolean
  provider: string
  model: string
  baseUrl: string
  llmKeyConfigured: boolean
}

export interface PlatformConfig {
  text: PlatformTextConfig
  assistant: PlatformAssistantConfig
}

export async function getPlatformConfig(): Promise<PlatformConfig> {
  const resp = await http.get('/admin/platform/config')
  return resp.data.data
}

/** 切换检测模型（推理服务同步重载 checkpoint，数秒到十几秒） */
export async function switchPlatformModel(payload: {
  checkpoint: string
  baseModelPath?: string
  modelVersion?: string
}): Promise<{ text: PlatformTextConfig }> {
  const resp = await http.post('/admin/platform/model/switch', payload)
  return resp.data.data
}

/** 更新助手 LLM 配置（字段 undefined=不改；apiKey 空串=清空） */
export async function updateAssistantConfig(payload: {
  baseUrl?: string
  model?: string
  apiKey?: string
  maxTokens?: number
}): Promise<{ assistant: PlatformAssistantConfig }> {
  const resp = await http.post('/admin/platform/assistant/config', payload)
  return resp.data.data
}
