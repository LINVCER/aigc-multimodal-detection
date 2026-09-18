<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadRawFile } from 'element-plus'
import { submitPaper, detectTextDirect, type DirectDetectResp } from '@/api/detect'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const router = useRouter()

// W3.b · 使用场景预设（取代原学位红线）
const SCENARIOS = [
  { key: 'academic_bachelor', label: '学术论文·本科', threshold: 20, desc: '毕业论文自查' },
  { key: 'academic_master',   label: '学术论文·硕士', threshold: 15, desc: '硕士毕业论文' },
  { key: 'academic_phd',      label: '学术论文·博士', threshold: 10, desc: '博士毕业论文' },
  { key: 'job_report',        label: '职业报告',       threshold: 15, desc: '工作报告 / 项目文档' },
  { key: 'self_media',        label: '自媒体',         threshold: 30, desc: '公众号 / 小红书 / 头条' },
  { key: 'other',             label: '其他',           threshold: 25, desc: '通用文档' },
] as const

type ScenarioKey = typeof SCENARIOS[number]['key']

const mode = ref<'file' | 'paste'>('file')
const scenario = ref<ScenarioKey>('academic_bachelor')
const file = ref<UploadRawFile | null>(null)
const submitting = ref(false)
const threshold = computed(() => SCENARIOS.find(s => s.key === scenario.value)?.threshold)

// 粘贴模式状态
const pasteText = ref('')
const pasteResult = ref<DirectDetectResp | null>(null)
const pasteChecking = ref(false)
const PASTE_MAX = 5000

function pasteBg(prob: number): string {
  if (prob >= 0.7) return 'rgba(255, 59, 48, 0.14)'
  if (prob >= 0.4) return 'rgba(255, 149, 0, 0.16)'
  return 'transparent'
}
function pasteColor(prob: number): string {
  if (prob >= 0.7) return 'var(--system-red)'
  if (prob >= 0.4) return 'var(--system-orange)'
  return 'var(--system-green)'
}

async function checkPaste() {
  if (!pasteText.value.trim()) return ElMessage.warning('请粘贴或输入文本')
  if (pasteText.value.length > PASTE_MAX) return ElMessage.warning(`文本超过 ${PASTE_MAX} 字，请分段检测`)
  pasteChecking.value = true
  pasteResult.value = null
  try {
    pasteResult.value = await detectTextDirect(pasteText.value)
  } finally { pasteChecking.value = false }
}
function clearPaste() { pasteText.value = ''; pasteResult.value = null }

function onChange(uploadFile: UploadFile) {
  const raw = uploadFile.raw
  if (!raw) return
  if (raw.size > 20 * 1024 * 1024) {
    ElMessage.warning('文件不能超过 20MB')
    file.value = null
    return
  }
  file.value = raw
}
function onRemove() { file.value = null }

function humanBytes(n?: number) {
  if (!n) return ''
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

async function submit() {
  if (!file.value) return ElMessage.warning('请先选择论文文件')
  submitting.value = true
  try {
    const resp = await submitPaper(file.value, scenario.value, undefined, auth.user?.id)
    ElMessage.success('提交成功，正在检测')
    router.push({ name: 'TaskDetail', params: { id: resp.taskId } })
  } finally { submitting.value = false }
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="header-title">上传检测</span>
        <span></span>
      </div>
    </el-header>

    <el-main class="main">
      <div class="wrap">
        <h1 class="large-title">上传检测</h1>

        <!-- Mode segmented (文件 / 粘贴) -->
        <div class="mode-tabs">
          <el-radio-group v-model="mode">
            <el-radio-button label="file"  value="file">📄 文件上传</el-radio-button>
            <el-radio-button label="paste" value="paste">✍ 粘贴文本</el-radio-button>
          </el-radio-group>
        </div>

        <!-- ===== 文件模式 ===== -->
        <template v-if="mode === 'file'">
          <div class="group-label">使用场景</div>
          <el-card class="group-card scenario-card">
            <div class="scenario-grid">
              <div
                v-for="s in SCENARIOS" :key="s.key"
                class="scenario-tile" :class="{ active: scenario === s.key }"
                @click="scenario = s.key"
              >
                <div class="scenario-label">{{ s.label }}</div>
                <div class="scenario-desc">{{ s.desc }}</div>
                <div class="scenario-th">建议 ≤ {{ s.threshold }}%</div>
              </div>
            </div>
            <div class="footnote">
              当前场景建议 AI 率 <span class="footnote-strong">≤ {{ threshold }}%</span>
            </div>
          </el-card>

          <div class="group-label">论文文件</div>
          <el-card class="group-card">
            <el-upload
              drag
              accept=".pdf,.doc,.docx,.txt"
              :auto-upload="false"
              :limit="1"
              :on-change="onChange"
              :on-remove="onRemove"
              :on-exceed="() => ElMessage.warning('只能选择一个文件')"
            >
              <div class="upload-inner">
                <div class="upload-icon">􀈕</div>
                <div class="upload-text">
                  <div class="upload-title">拖入文件 或 <em>点击选择</em></div>
                  <div class="upload-sub">PDF / Word / TXT · 最大 20MB</div>
                </div>
              </div>
            </el-upload>
            <div v-if="file" class="file-picked">
              <span class="file-name">{{ file.name }}</span>
              <span class="file-size">{{ humanBytes(file.size) }}</span>
            </div>
          </el-card>

          <el-button
            type="primary" round size="large"
            :loading="submitting" :disabled="!file"
            style="width: 100%; margin-top: 24px; height: 50px; font-size: 17px"
            @click="submit"
          >提交检测</el-button>

          <div class="privacy">
            论文原文加密存储，30 天后自动删除；检测报告保留 3 年
          </div>
        </template>

        <!-- ===== 粘贴模式 ===== -->
        <template v-else>
          <div class="group-label">
            段落文本
            <span class="paste-count" :class="{ over: pasteText.length > PASTE_MAX }">
              {{ pasteText.length }} / {{ PASTE_MAX }}
            </span>
          </div>
          <el-card class="group-card" body-style="padding: 12px">
            <el-input
              v-model="pasteText"
              type="textarea"
              :rows="10"
              placeholder="粘贴 50-5000 字的段落，即时看到 AI 率与句子级高亮"
              resize="vertical"
              maxlength="6000"
            />
          </el-card>

          <div class="paste-actions">
            <el-button plain round @click="clearPaste" :disabled="!pasteText && !pasteResult">清空</el-button>
            <el-button
              type="primary" round
              :loading="pasteChecking"
              :disabled="!pasteText.trim() || pasteText.length > PASTE_MAX"
              @click="checkPaste"
            >即时检测</el-button>
          </div>

          <!-- 粘贴结果 -->
          <template v-if="pasteResult">
            <div class="group-label">检测结果</div>
            <el-card class="group-card paste-result-card">
              <div class="paste-result-head">
                <div class="paste-result-rate" :style="{ color: pasteColor(pasteResult.calibratedProb) }">
                  {{ (pasteResult.calibratedProb * 100).toFixed(1) }}%
                </div>
                <div class="paste-result-meta">
                  <div class="paste-result-verdict" :style="{ color: pasteColor(pasteResult.calibratedProb) }">
                    <template v-if="pasteResult.riskLevel === 'high'">高疑似 AI 生成</template>
                    <template v-else-if="pasteResult.riskLevel === 'medium'">中等疑似</template>
                    <template v-else>判定人类写作</template>
                  </div>
                  <div v-if="pasteResult.warning" class="paste-result-warn">{{ pasteResult.warning }}</div>
                </div>
              </div>

              <div v-if="pasteResult.sentences.length" class="paste-highlight">
                <span
                  v-for="s in pasteResult.sentences" :key="s.sentenceIdx"
                  :style="{ background: pasteBg(s.aiProb) }"
                >{{ s.text }}</span>
              </div>

              <div v-if="pasteResult.branchScores" class="paste-branches">
                <span v-for="(v, k) in pasteResult.branchScores" :key="k" class="branch-chip">
                  {{ k }} <b>{{ (Number(v) * 100).toFixed(0) }}%</b>
                </span>
              </div>
            </el-card>
          </template>

          <div class="privacy">
            粘贴文本不落库、不生成任务，仅用于即时预览
          </div>
        </template>
      </div>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--label-quaternary);
  padding: 0; position: sticky; top: 0; z-index: 10;
}
.header-inner { height: 56px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.header-title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }

.main { padding: 32px 24px 48px; }
.wrap { max-width: 640px; margin: 0 auto; }

.large-title {
  font-size: var(--fs-large-title);
  font-weight: var(--fw-bold);
  letter-spacing: -0.8px;
  margin: 0 0 24px;
}

.group-label {
  font-size: var(--fs-caption-1);
  font-weight: var(--fw-medium);
  color: var(--label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 16px 12px 8px;
}
.group-card { margin-bottom: 8px; }

.footnote { margin-top: 12px; font-size: var(--fs-footnote); color: var(--label-secondary); }
.footnote-strong { color: var(--system-orange); font-weight: var(--fw-semibold); }

/* 场景网格 */
.scenario-card { padding: 0 !important; }
.scenario-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 20px;
}
.scenario-tile {
  padding: 14px 16px;
  border-radius: var(--radius-card);
  background: rgba(120, 120, 128, 0.08);
  cursor: pointer;
  border: 1.5px solid transparent;
  transition: all var(--dur-fast) var(--ease-standard);
}
.scenario-tile:hover { background: rgba(120, 120, 128, 0.14); }
.scenario-tile.active {
  border-color: var(--system-blue);
  background: rgba(0, 122, 255, 0.08);
}
.scenario-label { font-size: var(--fs-body); font-weight: var(--fw-semibold); color: var(--label); }
.scenario-desc  { font-size: var(--fs-caption-1); color: var(--label-secondary); margin-top: 4px; }
.scenario-th    { font-size: var(--fs-caption-1); color: var(--system-orange); margin-top: 6px; font-weight: var(--fw-medium); }

@media (max-width: 640px) {
  .scenario-grid { grid-template-columns: repeat(2, 1fr); }
}

.upload-inner {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 0;
}
.upload-icon {
  width: 48px; height: 48px; border-radius: 10px;
  background: rgba(0, 122, 255, 0.10);
  color: var(--system-blue);
  font-size: 22px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.upload-text { text-align: left; }
.upload-title { font-size: var(--fs-body); font-weight: var(--fw-medium); color: var(--label); }
.upload-title em { color: var(--system-blue); font-style: normal; font-weight: var(--fw-semibold); }
.upload-sub { font-size: var(--fs-caption-1); color: var(--label-secondary); margin-top: 4px; }

.file-picked {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(0, 122, 255, 0.06);
  border-radius: 8px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: var(--fs-subhead);
}
.file-name { color: var(--label); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { color: var(--label-secondary); flex-shrink: 0; margin-left: 12px; }

.privacy {
  margin-top: 24px;
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
  text-align: center;
}

/* Mode Tabs */
.mode-tabs {
  display: flex;
  justify-content: center;
  margin-bottom: 24px;
}

/* Paste 模式 */
.paste-count {
  float: right;
  font-weight: var(--fw-medium);
  font-variant-numeric: tabular-nums;
  color: var(--label-secondary);
  text-transform: none;
  letter-spacing: 0;
}
.paste-count.over { color: var(--system-red); }

.paste-actions {
  display: flex; justify-content: flex-end; gap: 12px;
  margin-top: 16px; margin-bottom: 8px;
}

.paste-result-card {}
.paste-result-head {
  display: flex; align-items: center; gap: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--label-quaternary);
  margin-bottom: 16px;
}
.paste-result-rate {
  font-size: 44px;
  font-weight: var(--fw-bold);
  letter-spacing: -1px;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.paste-result-meta { flex: 1; }
.paste-result-verdict { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }
.paste-result-warn { font-size: var(--fs-caption-1); color: var(--label-secondary); margin-top: 4px; }

.paste-highlight {
  font-size: 15px;
  line-height: 1.75;
  color: var(--label);
}

.paste-branches {
  margin-top: 16px;
  display: flex; flex-wrap: wrap; gap: 8px;
}
.branch-chip {
  background: rgba(120, 120, 128, 0.14);
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
  font-variant-numeric: tabular-nums;
}
.branch-chip b { color: var(--label); font-weight: var(--fw-semibold); margin-left: 4px; }
</style>
