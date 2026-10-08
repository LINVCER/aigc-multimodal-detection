<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadRawFile } from 'element-plus'
import { submitPaper, detectTextDirect, listTasks, type DirectDetectResp } from '@/api/detect'
import type { DetectTask } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

/**
 * 论文检测 · 上传页（只做论文）
 * 左：场景 + 投放区 + 修改稿对比 + CTA；右：说明 / 最近检测。窄屏折叠为单列。
 */

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const SCENARIOS = [
  { key: 'academic_bachelor', label: '学术·本科', threshold: 20, desc: '毕业论文自查', tint: '#007AFF' },
  { key: 'academic_master',   label: '学术·硕士', threshold: 15, desc: '硕士毕业论文', tint: '#5856D6' },
  { key: 'academic_phd',      label: '学术·博士', threshold: 10, desc: '博士毕业论文', tint: '#AF52DE' },
  { key: 'job_report',        label: '职业报告',   threshold: 15, desc: '工作报告 / 项目文档', tint: '#00C7BE' },
  { key: 'self_media',        label: '自媒体',     threshold: 30, desc: '公众号 / 小红书 / 头条', tint: '#FF2D55' },
  { key: 'other',             label: '其他',       threshold: 25, desc: '通用文档', tint: '#8E8E93' },
] as const
type ScenarioKey = typeof SCENARIOS[number]['key']
const SCENARIO_LABEL: Record<string, string> = Object.fromEntries(SCENARIOS.map((s) => [s.key, s.label]))

const mode = ref<'file' | 'paste'>(route.query.mode === 'paste' ? 'paste' : 'file')
const scenario = ref<ScenarioKey>('academic_bachelor')
const sc = computed(() => SCENARIOS.find((s) => s.key === scenario.value) || SCENARIOS[0])
const file = ref<UploadRawFile | null>(null)
const submitting = ref(false)
const dragOver = ref(false)
const FILE_MAX = 20 * 1024 * 1024
const PASTE_MAX = 5000

/* 修改稿对比 + 最近检测 */
const prevTasks = ref<DetectTask[]>([])
const recent = ref<DetectTask[]>([])
const parentTaskId = ref<number | undefined>(undefined)
const parentTask = computed(() => prevTasks.value.find((t) => t.id === parentTaskId.value))
onMounted(async () => {
  try {
    const page = await listTasks({ pageNum: 1, pageSize: 50 })
    const rows = page.rows || []
    prevTasks.value = rows.filter((t) => t.status === 'DONE').slice(0, 20)
    recent.value = rows.slice(0, 5)
  } catch { prevTasks.value = []; recent.value = [] }
})

/* ---------- 文件 ---------- */
function acceptRaw(raw: File | UploadRawFile | undefined) {
  if (!raw) return
  if (!/\.(pdf|docx?|txt)$/i.test(raw.name)) { ElMessage.warning('只支持 PDF / Word / TXT'); return }
  if (raw.size > FILE_MAX) { ElMessage.warning('文件不能超过 20MB'); return }
  file.value = raw as UploadRawFile
}
function onChange(uploadFile: UploadFile) { acceptRaw(uploadFile.raw) }
function onDrop(e: DragEvent) {
  dragOver.value = false
  acceptRaw(e.dataTransfer?.files?.[0])
}
function humanBytes(n?: number) {
  if (!n) return ''
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}
function extOf(name: string) { return name.split('.').pop()?.toUpperCase().slice(0, 4) || 'DOC' }

async function submit() {
  if (!file.value) return ElMessage.warning('请先选择论文文件')
  submitting.value = true
  try {
    const resp = await submitPaper(file.value, scenario.value, undefined, auth.user?.id, parentTaskId.value)
    ElMessage.success('已提交，正在检测')
    router.push({ name: 'TaskDetail', params: { id: resp.taskId } })
  } finally { submitting.value = false }
}

/* ---------- 粘贴 ---------- */
const pasteText = ref('')
const pasteResult = ref<DirectDetectResp | null>(null)
const pasteChecking = ref(false)
const pasteTooLong = computed(() => pasteText.value.length > PASTE_MAX)
const pasteShort = computed(() => pasteText.value.trim().length > 0 && pasteText.value.trim().length < 120)
function pasteBg(prob: number) { return prob >= 0.7 ? 'rgba(255, 59, 48, 0.14)' : prob >= 0.4 ? 'rgba(255, 149, 0, 0.16)' : 'transparent' }
function pasteColor(prob: number) { return prob >= 0.7 ? 'var(--system-red)' : prob >= 0.4 ? 'var(--system-orange)' : 'var(--system-green)' }
const pasteVerdict = computed(() => {
  const r = pasteResult.value
  if (!r) return null
  const lvl = r.riskLevel
  return {
    label: lvl === 'high' ? '高疑似 AI 生成' : lvl === 'medium' ? '中等疑似' : '更像人写',
    hint: lvl === 'high' ? '这一段很可能被判 AI，建议用自己的话重写核心观点' : lvl === 'medium' ? '处在灰区，补充具体细节与个人判断会更稳' : '继续保持，具体、有细节的写法最不像机器',
  }
})
async function checkPaste() {
  if (!pasteText.value.trim()) return ElMessage.warning('请粘贴或输入文本')
  if (pasteTooLong.value) return ElMessage.warning(`超过 ${PASTE_MAX} 字，请分段检测`)
  pasteChecking.value = true
  pasteResult.value = null
  try { pasteResult.value = await detectTextDirect(pasteText.value) }
  finally { pasteChecking.value = false }
}
function clearPaste() { pasteText.value = ''; pasteResult.value = null }
async function pasteFromClipboard() {
  try { const t = await navigator.clipboard.readText(); if (t) { pasteText.value = t.slice(0, PASTE_MAX + 500); pasteResult.value = null } }
  catch { ElMessage.warning('浏览器未授权读取剪贴板，请手动粘贴') }
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="header-title">论文检测</span>
        <span></span>
      </div>
    </el-header>

    <el-main class="main">
      <div class="wrap">
        <div class="hero">
          <h1 class="large-title">论文检测</h1>
          <p class="large-sub">上传全文出完整报告，或粘贴一段即时看结果。只做论文，不做音频与图像。</p>
          <div class="seg">
            <button class="seg-item" :class="{ active: mode === 'file' }" @click="mode = 'file'">📄 上传论文</button>
            <button class="seg-item" :class="{ active: mode === 'paste' }" @click="mode = 'paste'">✍️ 粘贴一段</button>
          </div>
        </div>

        <div class="grid">
          <!-- ===================== 主列 ===================== -->
          <div class="col-main">
            <template v-if="mode === 'file'">
              <!-- 场景 -->
              <div class="group-head">
                <span class="group-label">使用场景</span>
                <span class="group-hint">红线 <b :style="{ color: sc.tint }">≤ {{ sc.threshold }}%</b> · 只影响红线，不影响检测</span>
              </div>
              <div class="sc-grid">
                <button
                  v-for="s in SCENARIOS" :key="s.key" class="sc" :class="{ active: scenario === s.key }"
                  :style="scenario === s.key ? { borderColor: s.tint, color: s.tint, background: s.tint + '14' } : {}"
                  @click="scenario = s.key"
                >
                  <span class="sc-label">{{ s.label }}</span>
                  <span class="sc-desc">{{ s.desc }}</span>
                  <span class="sc-th">≤ {{ s.threshold }}%</span>
                </button>
              </div>

              <!-- 投放区 -->
              <div
                v-if="!file" class="drop" :class="{ over: dragOver }"
                @dragover.prevent="dragOver = true" @dragleave="dragOver = false" @drop.prevent="onDrop"
              >
                <el-upload :auto-upload="false" :show-file-list="false" accept=".pdf,.doc,.docx,.txt" :on-change="onChange" class="drop-upload">
                  <div class="drop-inner">
                    <div class="drop-icon"><span class="drop-doc" /><span class="drop-plus">+</span></div>
                    <div class="drop-title">拖入论文，或 <em>点击选择</em></div>
                    <div class="drop-sub">PDF · Word · TXT，最大 20MB</div>
                    <div class="drop-badges">
                      <span>自动排除参考文献 / 图表</span><span>段落 + 句子级结果</span><span>疑似来源溯源</span>
                    </div>
                  </div>
                </el-upload>
              </div>
              <div v-else class="picked">
                <span class="picked-ext" :style="{ background: sc.tint + '14', color: sc.tint }">{{ extOf(file.name) }}</span>
                <div class="picked-main">
                  <div class="picked-name">{{ file.name }}</div>
                  <div class="picked-meta">{{ humanBytes(file.size) }} · {{ sc.label }} · 红线 {{ sc.threshold }}%</div>
                </div>
                <el-upload :auto-upload="false" :show-file-list="false" accept=".pdf,.doc,.docx,.txt" :on-change="onChange">
                  <el-button link type="primary">更换</el-button>
                </el-upload>
                <el-button link type="danger" @click="file = null">移除</el-button>
              </div>

              <!-- 修改稿对比 -->
              <div v-if="prevTasks.length" class="prev" :class="{ on: parentTask }">
                <div class="prev-head">
                  <div class="prev-title">这是修改稿？</div>
                  <div class="prev-sub">关联上一次，报告里直接看「比上次 −X%」和逐段变化</div>
                </div>
                <el-select v-model="parentTaskId" clearable placeholder="不关联" style="width: 100%">
                  <el-option v-for="t in prevTasks" :key="t.id" :value="t.id" :label="`${t.paperTitle} · ${t.aiRate == null ? '—' : t.aiRate.toFixed(1) + '%'} · ${t.createdAt}`" />
                </el-select>
              </div>

              <el-button type="primary" round size="large" class="cta" :class="{ ready: file }" :loading="submitting" :disabled="!file" @click="submit">
                {{ file ? '开始检测' : '先选择论文文件' }}
              </el-button>
              <div class="privacy">原文加密存储，30 天自动删除 · 报告保留 3 年</div>
            </template>

            <template v-else>
              <div class="group-head">
                <span class="group-label">段落文本</span>
                <span class="group-hint" :class="{ over: pasteTooLong }">{{ pasteText.length }} / {{ PASTE_MAX }}</span>
              </div>
              <div class="paste">
                <el-input v-model="pasteText" type="textarea" :rows="12" resize="vertical" :maxlength="PASTE_MAX + 500"
                  placeholder="粘贴 120–5000 字，立刻看到 AI 率、句子级高亮和疑似来源。不落库、不生成任务。" />
                <div class="paste-tools">
                  <el-button link type="primary" @click="pasteFromClipboard">📋 从剪贴板粘贴</el-button>
                  <el-button v-if="pasteText" link @click="clearPaste">清空</el-button>
                  <span class="flex-1" />
                  <el-button type="primary" round :loading="pasteChecking" :disabled="!pasteText.trim() || pasteTooLong" @click="checkPaste">即时检测</el-button>
                </div>
                <div v-if="pasteShort" class="paste-warn">不足 120 字时判定不可靠，结果仅供参考</div>
              </div>

              <div v-if="pasteResult && pasteVerdict" class="result">
                <div class="result-head">
                  <div class="result-rate-wrap">
                    <div class="result-rate" :style="{ color: pasteColor(pasteResult.calibratedProb) }">{{ (pasteResult.calibratedProb * 100).toFixed(1) }}<span class="result-unit">%</span></div>
                    <div class="result-cap">校准概率</div>
                  </div>
                  <div class="result-meta">
                    <div class="result-verdict" :style="{ color: pasteColor(pasteResult.calibratedProb) }">{{ pasteVerdict.label }}</div>
                    <div class="result-hint">{{ pasteVerdict.hint }}</div>
                    <div v-if="pasteResult.warning" class="result-warn">{{ pasteResult.warning }}</div>
                  </div>
                </div>
                <div v-if="pasteResult.sentences.length" class="result-text">
                  <span v-for="s in pasteResult.sentences" :key="s.sentenceIdx" :style="{ background: pasteBg(s.aiProb) }">{{ s.text }}</span>
                </div>
                <div class="result-legend"><i class="sw high" /> 高 <i class="sw mid" /> 中 <span class="flex-1" /> 按句着色</div>
                <div v-if="pasteResult.branchScores" class="result-branches">
                  <span v-for="(v, k) in pasteResult.branchScores" :key="k" class="branch">{{ k }} <b>{{ (Number(v) * 100).toFixed(0) }}%</b></span>
                </div>
                <div class="result-actions">
                  <el-button round @click="mode = 'file'">上传全文出报告</el-button>
                </div>
              </div>
              <div class="privacy">粘贴文本不落库、不生成任务，仅即时预览</div>
            </template>
          </div>

          <!-- ===================== 侧栏 ===================== -->
          <aside class="col-side">
            <div class="side-card">
              <div class="side-title">报告里有什么</div>
              <ul class="side-list">
                <li><b>整体 AI 率</b>与你所选场景的红线对比，一眼看达标</li>
                <li><b>段落热力</b>：每段校准概率 + 句子级高亮，知道先改哪里</li>
                <li><b>疑似来源</b>：GPT / 通义 / DeepSeek 等风格占比</li>
                <li><b>改进建议</b>与助手解读，不代写、不改写原文</li>
                <li>修改后再测，报告自动给出<b>逐段对比</b></li>
              </ul>
            </div>
            <div v-if="recent.length" class="side-card">
              <div class="side-title">最近检测</div>
              <div v-for="t in recent" :key="t.id" class="recent" @click="router.push({ name: 'TaskDetail', params: { id: t.id } })">
                <div class="recent-main">
                  <div class="recent-title">{{ t.paperTitle }}</div>
                  <div class="recent-meta">{{ t.createdAt }} · {{ SCENARIO_LABEL[t.scenario] || t.scenario }}</div>
                </div>
                <span v-if="t.status === 'DONE' && t.aiRate != null" class="recent-rate" :class="t.aiRate <= t.threshold ? 'ok' : 'bad'">{{ t.aiRate.toFixed(1) }}%</span>
                <span v-else class="recent-rate muted">{{ t.status === 'FAILED' ? '失败' : '检测中' }}</span>
              </div>
            </div>
            <div class="side-card soft">
              <div class="side-title">怎样最不像机器</div>
              <div class="side-text">具体数据、真实经历、有取舍的判断。句子长短交错，少用「首先 / 综上所述」这类套话。写完自己读一遍，像你说话的，就留下。</div>
            </div>
          </aside>
        </div>
      </div>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header {
  background: rgba(255, 255, 255, 0.72); backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--label-quaternary); padding: 0; position: sticky; top: 0; z-index: 10;
}
.header-inner { height: 56px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.header-title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }
.main { padding: 32px 24px 64px; background: linear-gradient(180deg, #EEF4FF 0%, transparent 260px); }
.wrap { max-width: 1040px; margin: 0 auto; }

.hero { margin-bottom: 20px; }
.large-title { font-size: var(--fs-large-title); font-weight: var(--fw-bold); letter-spacing: -0.8px; margin: 0; }
.large-sub { color: var(--label-secondary); margin: 6px 0 16px; font-size: var(--fs-subhead); }
.seg { display: inline-flex; padding: 3px; background: rgba(120, 120, 128, 0.12); border-radius: 12px; }
.seg-item { border: none; background: transparent; padding: 8px 18px; border-radius: 9px; font-size: var(--fs-subhead); font-weight: 500; color: var(--label-secondary); cursor: pointer; }
.seg-item.active { background: #fff; color: var(--label); font-weight: 600; box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08); }

.grid { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 24px; align-items: start; }
@media (max-width: 860px) { .grid { grid-template-columns: 1fr; } .col-side { order: 2; } }

.group-head { display: flex; justify-content: space-between; align-items: baseline; padding: 18px 4px 8px; }
.group-label { font-size: var(--fs-caption-1); font-weight: 500; color: var(--label-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
.group-hint { font-size: var(--fs-caption-1); color: var(--label-secondary); font-variant-numeric: tabular-nums; }
.group-hint.over { color: var(--system-red); }

.sc-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
@media (max-width: 640px) { .sc-grid { grid-template-columns: repeat(2, 1fr); } }
.sc { text-align: left; border: 1.5px solid transparent; background: #fff; border-radius: 12px; padding: 12px 14px; cursor: pointer; display: flex; flex-direction: column; gap: 2px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04); transition: all .15s; }
.sc:hover { transform: translateY(-1px); }
.sc-label { font-size: var(--fs-subhead); font-weight: 600; }
.sc-desc { font-size: 12px; color: var(--label-secondary); }
.sc-th { font-size: 12px; font-weight: 600; opacity: .8; margin-top: 2px; }

.drop { margin-top: 16px; border: 2px dashed rgba(0, 122, 255, 0.35); border-radius: 16px; background: rgba(255, 255, 255, 0.9); transition: all .15s; }
.drop.over { background: rgba(0, 122, 255, 0.08); border-color: var(--system-blue); }
.drop-upload :deep(.el-upload) { width: 100%; }
.drop-inner { padding: 40px 24px 28px; display: flex; flex-direction: column; align-items: center; text-align: center; cursor: pointer; }
.drop-icon { position: relative; width: 64px; height: 64px; margin-bottom: 12px; }
.drop-doc { position: absolute; left: 12px; top: 4px; width: 40px; height: 52px; border-radius: 6px; background: rgba(0, 122, 255, 0.10); border: 1.5px solid rgba(0, 122, 255, 0.45); }
.drop-plus { position: absolute; right: 0; bottom: 0; width: 26px; height: 26px; border-radius: 50%; background: var(--system-blue); color: #fff; font-weight: 700; line-height: 26px; box-shadow: 0 4px 12px rgba(0, 122, 255, 0.3); }
.drop-title { font-size: var(--fs-headline); font-weight: 600; }
.drop-title em { color: var(--system-blue); font-style: normal; }
.drop-sub { font-size: var(--fs-footnote); color: var(--label-secondary); margin-top: 4px; }
.drop-badges { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; margin-top: 14px; }
.drop-badges span { font-size: 11px; color: var(--label-secondary); background: rgba(120, 120, 128, 0.10); padding: 2px 8px; border-radius: 99px; }

.picked { margin-top: 16px; background: #fff; border-radius: 14px; padding: 14px 16px; display: flex; align-items: center; gap: 12px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04); }
.picked-ext { flex: none; width: 44px; height: 44px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
.picked-main { flex: 1; min-width: 0; }
.picked-name { font-weight: 500; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.picked-meta { font-size: 12px; color: var(--label-secondary); margin-top: 2px; }

.prev { margin-top: 12px; background: #fff; border-radius: 14px; padding: 14px 16px; border: 1.5px solid transparent; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04); }
.prev.on { border-color: rgba(0, 122, 255, 0.35); }
.prev-head { margin-bottom: 8px; }
.prev-title { font-weight: 600; font-size: var(--fs-subhead); }
.prev-sub { font-size: 12px; color: var(--label-secondary); }

.cta { width: 100%; margin-top: 20px; height: 50px; font-size: 17px; }
.privacy { margin-top: 10px; font-size: var(--fs-caption-1); color: var(--label-secondary); text-align: center; }

.paste { background: #fff; border-radius: 14px; padding: 12px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04); }
.paste-tools { display: flex; align-items: center; gap: 8px; margin-top: 10px; }
.flex-1 { flex: 1; }
.paste-warn { font-size: 12px; color: var(--system-orange); margin-top: 8px; }

.result { margin-top: 16px; background: #fff; border-radius: 14px; padding: 18px 20px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04); }
.result-head { display: flex; align-items: center; gap: 20px; padding-bottom: 14px; border-bottom: 1px solid var(--label-quaternary); margin-bottom: 14px; }
.result-rate-wrap { flex: none; text-align: center; }
.result-rate { font-size: 44px; font-weight: 700; letter-spacing: -1px; line-height: 1; font-variant-numeric: tabular-nums; }
.result-unit { font-size: 18px; font-weight: 600; margin-left: 2px; }
.result-cap { font-size: 11px; color: var(--label-secondary); margin-top: 4px; }
.result-meta { flex: 1; min-width: 0; }
.result-verdict { font-size: var(--fs-headline); font-weight: 600; }
.result-hint { font-size: var(--fs-footnote); color: var(--label-secondary); margin-top: 4px; line-height: 1.5; }
.result-warn { font-size: 12px; color: var(--system-orange); margin-top: 4px; }
.result-text { font-size: 15px; line-height: 1.75; }
.result-legend { display: flex; align-items: center; gap: 6px; margin-top: 8px; font-size: 12px; color: var(--label-secondary); }
.sw { display: inline-block; width: 14px; height: 7px; border-radius: 2px; }
.sw.high { background: rgba(255, 59, 48, 0.3); } .sw.mid { background: rgba(255, 149, 0, 0.3); margin-left: 8px; }
.result-branches { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.branch { background: rgba(120, 120, 128, 0.14); padding: 3px 10px; border-radius: 99px; font-size: 12px; color: var(--label-secondary); }
.branch b { color: var(--label); margin-left: 4px; }
.result-actions { margin-top: 14px; display: flex; gap: 8px; }

.col-side { display: flex; flex-direction: column; gap: 14px; }
.side-card { background: #fff; border-radius: 14px; padding: 16px 18px; box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04); }
.side-card.soft { background: rgba(0, 122, 255, 0.06); box-shadow: none; }
.side-title { font-weight: 600; margin-bottom: 8px; }
.side-list { margin: 0; padding-left: 18px; font-size: 13px; color: var(--label-secondary); line-height: 1.7; }
.side-list b { color: var(--label); font-weight: 600; }
.side-text { font-size: 13px; color: var(--label); line-height: 1.7; }
.recent { display: flex; align-items: center; gap: 10px; padding: 8px 0; border-top: 1px solid var(--label-quaternary); cursor: pointer; }
.recent:first-of-type { border-top: none; }
.recent-main { flex: 1; min-width: 0; }
.recent-title { font-size: 13px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.recent-meta { font-size: 11px; color: var(--label-secondary); }
.recent-rate { font-weight: 700; font-variant-numeric: tabular-nums; }
.recent-rate.ok { color: var(--system-green); } .recent-rate.bad { color: var(--system-red); } .recent-rate.muted { color: var(--label-secondary); font-weight: 500; font-size: 12px; }
</style>
