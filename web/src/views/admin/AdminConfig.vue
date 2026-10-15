<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ZyIcon from '@/components/ZyIcon.vue'
import { getPlatformConfig, switchPlatformModel, updateAssistantConfig, type PlatformConfig } from '@/api/platform'

const loading = ref(false)
const config = ref<PlatformConfig | null>(null)
const loadError = ref('')

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    config.value = await getPlatformConfig()
    fillLlm()
  } catch (e: any) {
    loadError.value = e?.message || '推理服务不可达'
  } finally { loading.value = false }
}
onMounted(load)

/* ---------- 检测模型切换 ---------- */
const modelForm = reactive<{ checkpoint: string; baseModelPath: string }>({ checkpoint: '', baseModelPath: '' })
const switching = ref(false)

const currentVersion = () => config.value?.text.detail?.model_version || '—'
const currentCkpt = () => config.value?.text.detail?.checkpoint_path || '—'
const currentBase = () => {
  const b = config.value?.text.detail?.backbone
  return b && !String(b).startsWith('D:/') ? String(b) : config.value?.text.detail?.backbone || ''
}

async function onSwitch() {
  if (!modelForm.checkpoint) { ElMessage.warning('先选一个 checkpoint'); return }
  const toLegacy = /backup|_v1|_v2|aigc_detector\.pth/.test(modelForm.checkpoint)
  try {
    await ElMessageBox.confirm(
      `将检测模型切换到「${modelForm.checkpoint}」？切换期间检测会短暂 fallback 到 stub，通常十几秒内完成。`,
      '切换检测模型',
      { type: 'warning', confirmButtonText: '切换', cancelButtonText: '再想想' },
    )
  } catch { return }
  switching.value = true
  try {
    const r = await switchPlatformModel({
      checkpoint: modelForm.checkpoint,
      // legacy checkpoint 必须带基座；新模型（ml/training 产出，文件名 v3+ 或带 fusion）传空清掉
      baseModelPath: toLegacy ? (modelForm.baseModelPath || currentBase()) : '',
    })
    config.value!.text = r.text
    modelForm.checkpoint = ''
    if (r.text.backend === 'real' && !r.text.load_error) {
      ElMessage.success(`已切换到 ${r.text.detail?.model_version}`)
    } else {
      ElMessage.error(`加载失败：${r.text.load_error}，已 fallback stub；请检查基座路径后重选`)
    }
  } finally { switching.value = false }
}

/* ---------- 助手 LLM 配置 ---------- */
const llmForm = reactive<{ baseUrl: string; model: string; apiKey: string; maxTokens: number | undefined }>({ baseUrl: '', model: '', apiKey: '', maxTokens: undefined })
const llmLoaded = ref(false)
const savingLlm = ref(false)

function fillLlm() {
  const a = config.value?.assistant
  if (!a) return
  llmForm.baseUrl = a.baseUrl || ''
  llmForm.model = a.model || ''
  llmForm.apiKey = ''
  llmForm.maxTokens = undefined
  llmLoaded.value = true
}

async function onSaveLlm() {
  savingLlm.value = true
  try {
    // apiKey 留空 = 不改（后端 null=不改，空串=清空），只提交填了的
    const payload: { baseUrl?: string; model?: string; apiKey?: string; maxTokens?: number } = {
      baseUrl: llmForm.baseUrl || undefined,
      model: llmForm.model || undefined,
    }
    if (llmForm.apiKey) payload.apiKey = llmForm.apiKey
    if (llmForm.maxTokens && llmForm.maxTokens > 0) payload.maxTokens = llmForm.maxTokens
    const r = await updateAssistantConfig(payload)
    config.value!.assistant = r.assistant
    fillLlm()
    ElMessage.success('助手配置已保存，即时生效')
  } finally { savingLlm.value = false }
}
</script>

<template>
  <div class="page-head">
    <div>
      <div class="page-title">参数配置</div>
      <div class="page-sub">检测模型版本切换 · 助手 LLM API 配置；改动写回推理服务 .env，重启后仍生效</div>
    </div>
    <el-button @click="load">刷新</el-button>
  </div>

  <div v-if="loadError" class="card err-card">
    <ZyIcon name="alert" :size="18" />
    <div>
      <div class="err-title">推理服务不可达</div>
      <div class="muted small">{{ loadError }} · 检查 8000 端口（deploy/inference-python/start.ps1）后刷新</div>
    </div>
  </div>

  <div v-loading="loading" class="grid">
    <!-- ============ 检测模型 ============ -->
    <section class="card sec">
      <div class="sec-head">
        <span class="sec-icon"><ZyIcon name="flask" :size="17" /></span>
        <div>
          <div class="sec-title">AIGC 检测模型</div>
          <div class="muted small">当前版本与切换（对齐 MODEL_SWITCH.md：只改 .env，热重载）</div>
        </div>
        <el-tag v-if="config" class="ml-auto" :type="config.text.backend === 'real' ? 'success' : 'danger'" size="small">
          {{ config.text.backend === 'real' ? 'real' : 'stub' }}
        </el-tag>
      </div>

      <template v-if="config">
        <div class="kv"><span class="k">当前版本</span><span class="v mono">{{ currentVersion() }}</span></div>
        <div class="kv"><span class="k">权重文件</span><span class="v mono small-text">{{ currentCkpt() }}</span></div>
        <div class="kv"><span class="k">推理设备</span><span class="v mono">{{ config.text.detail?.device || '—' }}</span></div>
        <div v-if="config.text.load_error" class="load-err">加载失败：{{ config.text.load_error }}</div>

        <el-divider />
        <div class="field-label">切换到（models 目录：{{ config.text.modelsDir }}）</div>
        <el-select v-model="modelForm.checkpoint" placeholder="选择 checkpoint" class="field" filterable>
          <el-option v-for="c in config.text.checkpoints" :key="c" :label="c" :value="c" />
        </el-select>
        <div class="field-label muted small">legacy checkpoint（v1/v2/backup 等旧权重）需基座路径：</div>
        <el-input v-model="modelForm.baseModelPath" class="field" placeholder="默认沿用当前基座；如 models/text/chinese-roberta-wwm-ext" />
        <el-button type="primary" class="field" :loading="switching" @click="onSwitch">
          {{ switching ? '正在热重载…' : '切换模型' }}
        </el-button>
      </template>
    </section>

    <!-- ============ 助手 LLM ============ -->
    <section class="card sec">
      <div class="sec-head">
        <span class="sec-icon"><ZyIcon name="xiaobai-spark" :size="17" /></span>
        <div>
          <div class="sec-title">助手 LLM API</div>
          <div class="muted small">小白对话与反馈草稿走这套配置，保存即热生效</div>
        </div>
        <el-tag v-if="config" class="ml-auto" :type="config.assistant.enabled ? 'success' : 'info'" size="small">
          {{ config.assistant.provider }}
        </el-tag>
      </div>

      <template v-if="config && llmLoaded">
        <div class="kv"><span class="k">API Key</span><span class="v">{{ config.assistant.llmKeyConfigured ? '已配置' : '未配置' }}</span></div>
        <div class="field-label">Base URL</div>
        <el-input v-model="llmForm.baseUrl" class="field" placeholder="如 https://api.deepseek.com" />
        <div class="field-label">模型名</div>
        <el-input v-model="llmForm.model" class="field" placeholder="如 deepseek-flash" />
        <div class="field-label">API Key <span class="muted small">（{{ config.assistant.llmKeyConfigured ? '已配置，留空保持不变' : '未配置' }}）</span></div>
        <el-input v-model="llmForm.apiKey" class="field" type="password" show-password autocomplete="new-password" placeholder="留空 = 不改" />
        <div class="field-label">单次回复上限 tokens <span class="muted small">（留空 = 不改）</span></div>
        <el-input-number v-model="llmForm.maxTokens" class="field" :min="100" :max="8000" placeholder="默认 800" />
        <el-button type="primary" class="field" :loading="savingLlm" @click="onSaveLlm">保存</el-button>
      </template>
    </section>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 16px; align-items: start; }
.card { background: var(--system-background); border: 1px solid rgba(23, 24, 28, 0.08); border-radius: var(--radius-card); box-shadow: 0 2px 8px rgba(23, 24, 28, 0.05); padding: 20px; }
.err-card { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; border-color: rgba(229, 72, 77, 0.35); }
.err-card .zy-icon { color: var(--danger); flex: none; }
.err-title { font-weight: 600; color: var(--danger); }
.sec-head { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
.sec-icon { width: 36px; height: 36px; border-radius: 12px; background: var(--ai-100); color: var(--ai-700); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.sec-title { font-size: 16px; font-weight: 600; }
.ml-auto { margin-left: auto; }
.kv { display: flex; gap: 12px; padding: 6px 0; font-size: 14px; }
.kv .k { flex: none; width: 76px; color: var(--label-secondary); }
.kv .v { word-break: break-all; }
.mono { font-family: ui-monospace, Consolas, monospace; }
.small-text { font-size: 12px; }
.load-err { margin-top: 8px; padding: 8px 12px; border-radius: 10px; background: rgba(229, 72, 77, 0.08); color: var(--danger); font-size: 13px; }
.field-label { margin: 12px 0 6px; font-size: 13px; font-weight: 500; }
.field { width: 100%; margin-bottom: 4px; }
.field.el-button { margin-top: 12px; }
</style>
