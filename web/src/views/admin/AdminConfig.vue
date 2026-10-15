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
      <div class="page-sub">检测模型与助手 LLM 的运行参数；改动写回推理服务 .env，重启后仍生效</div>
    </div>
    <el-button :icon="null" @click="load"><ZyIcon name="rotate" :size="14" />&nbsp;刷新</el-button>
  </div>

  <div v-if="loadError" class="card err-card">
    <ZyIcon name="alert" :size="18" />
    <div>
      <div class="err-title">推理服务不可达</div>
      <div class="muted small">{{ loadError }} · 检查 8000 端口（deploy/inference-python/start.ps1）后刷新</div>
    </div>
  </div>

  <div v-loading="loading" class="grid">
    <!-- ============ AIGC 检测模型（当前版本为数据主角；切换属危险操作，独立分区） ============ -->
    <section class="card sec">
      <div class="sec-head">
        <span class="sec-icon"><ZyIcon name="flask" :size="17" /></span>
        <div class="sec-head-text">
          <div class="sec-title">AIGC 检测模型</div>
          <div class="muted small">所有检测报告由它产出，切换即全局生效</div>
        </div>
        <span v-if="config" class="state-badge" :class="config.text.backend === 'real' ? 'ok' : 'bad'">
          <i class="dot" />{{ config.text.backend === 'real' ? 'real · 正常推理' : 'stub · 占位返回' }}
        </span>
      </div>

      <template v-if="config">
        <!-- 当前版本 hero -->
        <div class="model-hero">
          <div class="model-version mono">{{ currentVersion() }}</div>
          <div class="model-ckpt mono">{{ currentCkpt() }}</div>
          <div class="model-meta">
            <span class="meta-chip mono"><ZyIcon name="tool" :size="12" />{{ config.text.detail?.device || '—' }}</span>
            <span v-if="config.text.detail?.backbone" class="meta-chip mono">legacy 基座</span>
            <span class="meta-chip">{{ config.text.checkpoints.length }} 个候选权重</span>
          </div>
        </div>
        <div v-if="config.text.load_error" class="load-err">
          <ZyIcon name="alert" :size="14" />加载失败：{{ config.text.load_error }} · 当前所有检测走 stub，请尽快切换或修复
        </div>

        <!-- 切换操作区：危险操作，独立浅底分区 + 警示说明 -->
        <div class="op-zone">
          <div class="op-zone-title">
            <span>切换到其它版本</span>
            <span class="op-zone-warn">切换期间检测短暂 fallback 到 stub，通常十几秒完成</span>
          </div>
          <el-select v-model="modelForm.checkpoint" placeholder="选择 checkpoint（models 目录下）" class="field" filterable>
            <el-option v-for="c in config.text.checkpoints" :key="c" :label="c" :value="c" />
          </el-select>
          <div class="field-label">legacy checkpoint（v1 / v2 / backup 等旧权重）需基座路径</div>
          <el-input v-model="modelForm.baseModelPath" class="field" placeholder="默认沿用当前基座；如 models/text/chinese-roberta-wwm-ext" />
          <el-button type="primary" class="field switch-btn" :loading="switching" @click="onSwitch">
            <ZyIcon v-if="!switching" name="rotate" :size="14" />&nbsp;{{ switching ? '正在热重载…' : '切换模型' }}
          </el-button>
        </div>
      </template>
    </section>

    <!-- ============ 助手 LLM API（常规配置） ============ -->
    <section class="card sec">
      <div class="sec-head">
        <span class="sec-icon xiaobai"><ZyIcon name="xiaobai-spark" :size="17" /></span>
        <div class="sec-head-text">
          <div class="sec-title">助手 LLM API</div>
          <div class="muted small">小白对话与反馈草稿走这套配置，保存即热生效</div>
        </div>
        <span v-if="config" class="state-badge ok"><i class="dot" />{{ config.assistant.provider }}</span>
      </div>

      <template v-if="config && llmLoaded">
        <div class="llm-status-row">
          <span class="meta-chip mono">{{ config.assistant.model }}</span>
          <span class="meta-chip mono">{{ config.assistant.baseUrl }}</span>
          <span class="meta-chip" :class="config.assistant.llmKeyConfigured ? 'ok-chip' : 'bad-chip'">
            <i class="dot" />{{ config.assistant.llmKeyConfigured ? 'API Key 已配置' : 'API Key 未配置' }}
          </span>
        </div>

        <div class="op-zone">
          <div class="op-zone-title"><span>修改配置</span><span class="op-zone-warn">留空的项保持不变</span></div>
          <div class="field-label">Base URL</div>
          <el-input v-model="llmForm.baseUrl" class="field" placeholder="如 https://api.deepseek.com" />
          <div class="field-label">模型名</div>
          <el-input v-model="llmForm.model" class="field" placeholder="如 deepseek-flash" />
          <div class="field-label">API Key</div>
          <el-input v-model="llmForm.apiKey" class="field" type="password" show-password autocomplete="new-password" :placeholder="config.assistant.llmKeyConfigured ? '已配置，留空保持不变' : '未配置'" />
          <div class="field-label">单次回复上限 tokens</div>
          <el-input-number v-model="llmForm.maxTokens" class="field" :min="100" :max="8000" placeholder="默认 800" />
          <el-button type="primary" class="field switch-btn" :loading="savingLlm" @click="onSaveLlm">保存</el-button>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; align-items: start; }
.card { background: var(--system-background); border: 1px solid rgba(23, 24, 28, 0.08); border-radius: var(--radius-card); box-shadow: 0 2px 8px rgba(23, 24, 28, 0.05); padding: 20px; }
.muted { color: var(--label-secondary); }
.small { font-size: 12px; }
.mono { font-family: ui-monospace, Consolas, monospace; font-variant-numeric: tabular-nums; }

/* 推理服务不可达 */
.err-card { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; border-color: rgba(229, 72, 77, 0.35); }
.err-card .zy-icon { color: var(--danger); flex: none; }
.err-title { font-weight: 600; color: var(--danger); }

/* 卡片头：图标圆片 + 标题 + 状态徽章 */
.sec-head { display: flex; gap: 12px; align-items: flex-start; margin-bottom: 16px; }
.sec-icon { width: 36px; height: 36px; border-radius: 12px; background: var(--ai-100); color: var(--ai-700); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.sec-icon.xiaobai { color: var(--ai-500); }
.sec-head-text { flex: 1; min-width: 0; }
.sec-title { font-size: 16px; font-weight: 600; }

/* 状态徽章：real/stub 与 provider 一眼可辨 */
.state-badge { flex: none; display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: var(--radius-pill); }
.state-badge .dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; }
.state-badge.ok { background: rgba(22, 163, 74, 0.10); color: #15803d; }
.state-badge.bad { background: rgba(229, 72, 77, 0.10); color: var(--danger); }

/* 当前版本 hero：页面数据主角 */
.model-hero { padding: 16px; border-radius: 12px; background: var(--bg-deep); }
.model-version { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; color: var(--ai-700); word-break: break-all; }
.model-ckpt { margin-top: 6px; font-size: 12px; color: var(--label-secondary); word-break: break-all; }
.model-meta { margin-top: 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.meta-chip { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; padding: 2px 8px; border-radius: var(--radius-pill); background: var(--system-background); border: 1px solid rgba(23, 24, 28, 0.10); color: var(--label-secondary); }
.meta-chip .zy-icon { color: var(--ai-700); }
.meta-chip.ok-chip { border-color: rgba(22, 163, 74, 0.35); color: #15803d; }
.meta-chip.bad-chip { border-color: rgba(229, 72, 77, 0.35); color: var(--danger); }

/* stub / 加载失败警示 */
.load-err { margin-top: 10px; display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 10px; background: rgba(229, 72, 77, 0.08); color: var(--danger); font-size: 13px; line-height: 1.5; }
.load-err .zy-icon { flex: none; }

/* LLM 当前状态行 */
.llm-status-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }

/* 操作分区：浅底圆角块把「改配置」与「读状态」分开 */
.op-zone { margin-top: 14px; padding: 14px; border-radius: 12px; border: 1px dashed rgba(23, 24, 28, 0.14); background: rgba(250, 249, 246, 0.6); }
.op-zone-title { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 10px; font-size: 13px; font-weight: 600; }
.op-zone-warn { font-size: 11px; font-weight: 400; color: var(--label-tertiary); }
.field-label { margin: 10px 0 6px; font-size: 12px; font-weight: 500; color: var(--label-secondary); }
.op-zone .field-label:first-of-type { margin-top: 0; }
.field { width: 100%; }
.switch-btn { margin-top: 14px; }
</style>
