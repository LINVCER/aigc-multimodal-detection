<template>
  <div class="reduce-page">
    <h1>一键论文降 AIGC</h1>
    <p style="color:#718096;margin-top:0">上传论文文档，智能优化降低 AI 检测率</p>

    <el-card>
      <div class="upload-zone" :class="{ 'drag-over': dragOver, 'has-file': reduceFile }"
        @click="!reduceFile && triggerFileUpload()"
        @dragover.prevent="dragOver=true"
        @dragleave="dragOver=false"
        @drop.prevent="handleFileDrop">
        <div v-if="!reduceFile">
          <el-icon :size="40" color="#a0aec0"><UploadFilled /></el-icon>
          <p class="upload-title">拖拽论文文档到此处或点击选择</p>
          <p class="upload-hint">支持 .txt / .docx 格式，最大 20MB</p>
        </div>
        <div v-else class="file-card">
          <div class="file-icon-box">
            <el-icon :size="28" :color="fileExt === 'docx' ? '#2b579a' : '#4a5568'">
              <Document v-if="fileExt === 'docx'" /><Tickets v-else />
            </el-icon>
          </div>
          <div class="file-info">
            <div class="file-name">{{ reduceFile.name }}</div>
            <div class="file-meta">{{ formatSize(reduceFile.size) }} · {{ fileExt.toUpperCase() }}</div>
          </div>
          <el-button size="small" circle type="danger" :icon="Close" @click.stop="reduceFile=null;report=null" />
        </div>
        <input ref="reduceFileInput" type="file" accept=".txt,.docx" style="display:none" @change="handleReduceFileInput" />
      </div>

      <div style="margin-top:12px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <el-button type="primary" size="large" @click="handleReduce" :loading="reducing" :disabled="!reduceFile">
          <el-icon><MagicStick /></el-icon> {{ reducing ? '智能优化中...' : '一键降 AI' }}
        </el-button>
        <el-select v-model="maxIter" style="width:140px">
          <el-option :value="1" label="快速 (1轮)" /><el-option :value="2" label="标准 (2轮)" /><el-option :value="3" label="深度 (3轮)" />
        </el-select>
      </div>
    </el-card>

    <!-- 结果 -->
    <div v-if="report" class="results" style="margin-top:20px">
      <div style="display:flex;gap:16px">
        <el-card class="verdict-card" style="flex:1;text-align:center">
          <div style="font-size:13px;color:#a0aec0;margin-bottom:4px">优化前</div>
          <el-tag :type="report.original_is_ai?'danger':'success'" size="large">{{ report.original_is_ai?'AI 生成':'人类写作' }}</el-tag>
          <div style="font-size:28px;font-weight:800;margin-top:8px" :style="{color:report.original_confidence>0.3?'#dc2626':'#10b981'}">{{ (report.original_confidence*100).toFixed(1) }}%</div>
        </el-card>
        <div style="display:flex;align-items:center;font-size:24px;color:#a0aec0;padding:0 8px"><el-icon><DArrowRight /></el-icon></div>
        <el-card class="verdict-card" style="flex:1;text-align:center" :style="{borderLeft:'4px solid '+(report.final_is_ai?'#dc2626':'#10b981')}">
          <div style="font-size:13px;color:#a0aec0;margin-bottom:4px">优化后</div>
          <el-tag :type="report.final_is_ai?'danger':'success'" size="large">{{ report.final_is_ai?'AI 生成':'人类写作' }}</el-tag>
          <div style="font-size:28px;font-weight:800;margin-top:8px" :style="{color:report.final_confidence>0.3?'#dc2626':'#10b981'}">{{ (report.final_confidence*100).toFixed(1) }}%</div>
          <div style="font-size:14px;font-weight:600;margin-top:4px" :style="{color:report.reduction_rate>0?'#10b981':'#dc2626'}">{{ report.reduction_rate>0?'↓':'' }}{{ report.reduction_rate }}%</div>
        </el-card>
      </div>

      <el-card style="margin-top:16px">
        <el-alert :type="report.final_confidence<0.3?'success':report.reduction_rate>20?'warning':'error'" :title="report.verdict" :closable="false" show-icon />
      </el-card>

      <el-card v-if="report.feature_gaps?.length" style="margin-top:16px">
        <template #header><span style="font-weight:600">特征差距分析</span></template>
        <div style="font-size:13px;color:#718096;margin-bottom:12px">以下特征对 AI 检测贡献最高，优化将针对性处理</div>
        <div v-for="g in report.feature_gaps.slice(0, 6)" :key="g.feature_name" class="feature-gap-item">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:600;font-size:14px">{{ featureNameMap[g.feature_name] || g.feature_name }}</span>
            <div style="display:flex;gap:8px;align-items:center">
              <el-progress :percentage="Math.round(g.ai_contribution*100)" :stroke-width="8" style="width:100px"
                :color="g.ai_contribution>0.6?'#dc2626':g.ai_contribution>0.3?'#f59e0b':'#10b981'" />
              <el-tag size="small" :type="g.ai_contribution>0.6?'danger':g.ai_contribution>0.3?'warning':'success'">
                AI贡献 {{ (g.ai_contribution*100).toFixed(0) }}%
              </el-tag>
            </div>
          </div>
          <div v-if="g.suggestion" style="font-size:12px;color:#a0aec0;margin-top:4px">{{ g.suggestion }}</div>
        </div>
      </el-card>

      <el-card v-if="report.steps?.length" style="margin-top:16px">
        <template #header><span style="font-weight:600">优化步骤</span></template>
        <div v-for="(s,i) in report.steps" :key="i" class="step-item">
          <div style="display:flex;align-items:center;gap:8px">
            <el-tag size="small" :type="s.error?'danger':s.rolled_back?'warning':s.delta<0?'success':'info'">
              {{ s.error?'失败':s.rolled_back?'已回滚':s.delta<0?'改善':'无变化' }}
            </el-tag>
            <span style="font-weight:600;font-size:14px">{{ s.step }}</span>
          </div>
          <div style="font-size:13px;color:#718096;margin-top:4px">
            <template v-if="s.error">{{ s.error }}</template>
            <template v-else>
              AI率: {{ (s.confidence*100).toFixed(1) }}%
              <span v-if="s.delta!==0" :style="{color:s.delta<0?'#10b981':'#dc2626',marginLeft:'8px'}">
                {{ s.delta>0?'+':'' }}{{ (s.delta*100).toFixed(1) }}%
              </span>
              <span v-if="s.rolled_back" style="color:#f59e0b;margin-left:8px">(AI率升高，已回滚)</span>
            </template>
          </div>
          <div v-if="s.changes?.length" style="margin-top:4px">
            <div v-for="c in s.changes" :key="c.description" style="font-size:12px;color:#a0aec0;padding-left:12px">
              · {{ c.description }}
            </div>
          </div>
        </div>
      </el-card>

      <el-card v-if="report.changes?.length" style="margin-top:16px">
        <template #header><span style="font-weight:600">改写详情</span></template>
        <div v-for="c in report.changes" :key="c.type" class="change-item">
          <el-tag size="small" :type="c.icon==='delete'?'danger':c.icon==='plus'?'success':'info'">{{ c.icon==='delete'?'已移除':c.icon==='plus'?'已添加':'已优化' }}</el-tag>
          <span style="margin-left:8px;font-size:14px;color:#4a5568">
            <template v-if="c.type==='slop_removed'">移除 {{ c.count }} 个 AI 标志词</template>
            <template v-else-if="c.type==='sentences_split'">句式重构: {{ c.before }}句 → {{ c.after }}句</template>
            <template v-else-if="c.type==='specific_data_added'">增加 {{ c.count }} 处具体数据</template>
          </span>
        </div>
      </el-card>

      <el-card v-if="report.optimized_text" style="margin-top:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:600">优化后文本</span>
            <div style="display:flex;gap:8px">
              <el-button size="small" type="primary" @click="downloadPdf"><el-icon><Download /></el-icon> PDF</el-button>
              <el-button size="small" type="success" @click="downloadDocx"><el-icon><Download /></el-icon> Word</el-button>
              <el-button size="small" @click="downloadTxt"><el-icon><Document /></el-icon> TXT</el-button>
              <el-button size="small" @click="copyText"><el-icon><CopyDocument /></el-icon> 复制</el-button>
            </div>
          </div>
        </template>
        <div class="optimized-text">{{ report.optimized_text }}</div>
      </el-card>

      <el-card v-if="report.report_document" style="margin-top:16px">
        <template #header><span style="font-weight:600">完整报告</span></template>
        <pre class="report-preview">{{ report.report_document }}</pre>
      </el-card>
    </div>

    <el-card style="margin-top:16px">
      <template #header><span style="font-weight:600">工作原理</span></template>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;font-size:13px;color:#4a5568">
        <div><strong>1. 特征分析</strong><br/>提取 19 项统计特征，识别贡献 AI 率最高的特征</div>
        <div><strong>2. 结构扰动</strong><br/>句长变异、节奏扰动、过渡词替换、重复率降低</div>
        <div><strong>3. 局部人类化</strong><br/>过程描述、括号补充、经验表达、弱化绝对表述</div>
        <div><strong>4. LLM 特征感知改写</strong><br/>根据特征差距动态生成 prompt，针对性改写</div>
        <div><strong>5. 每步检测 + 回滚</strong><br/>每步变换后重新检测，AI率升高则自动回滚</div>
        <div><strong>6. 迭代优化</strong><br/>多轮改写直到 AI 率低于阈值或无法继续降低</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed as vueComputed } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { MagicStick, DArrowRight, Download, CopyDocument, Document, UploadFilled, Tickets, Close } from "@element-plus/icons-vue"
import { formatSize } from "@/utils/format"

const reduceFile = ref<File | null>(null)
const reduceFileInput = ref<HTMLInputElement>()
const reducing = ref(false)
const downloadingPdf = ref(false)
const downloadingDocx = ref(false)
const report = ref<any>(null)
const maxIter = ref(2)

const featureNameMap: Record<string, string> = {
  slop_word_density: "AI标志词密度",
  transition_word_density: "过渡词密度",
  idiom_density: "成语密度",
  bigram_repetition_rate: "短语重复率",
  sentence_length_cv: "句长变异系数",
  burstiness: "句子复杂度变异",
  punctuation_entropy: "标点熵",
  unigram_entropy: "字频熵",
  zipf_deviation: "Zipf偏差",
  hapax_ratio: "低频词比率",
  yule_k: "词汇集中度",
}
const dragOver = ref(false)

const fileExt = vueComputed(() => {
  if (!reduceFile.value) return ""
  return reduceFile.value.name.split(".").pop()?.toLowerCase() || ""
})

function triggerFileUpload() { if (!reduceFile.value) reduceFileInput.value?.click() }
function handleReduceFileInput(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files?.length) {
    const f = t.files[0]
    const ext = f.name.split(".").pop()?.toLowerCase()
    if (ext === "txt" || ext === "docx") { reduceFile.value = f; report.value = null }
    else { ElMessage.warning("仅支持 .txt / .docx 格式") }
  }
  t.value = ""
}
function handleFileDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    const f = files[0]
    const ext = f.name.split(".").pop()?.toLowerCase()
    if (ext === "txt" || ext === "docx") { reduceFile.value = f; report.value = null }
    else { ElMessage.warning("仅支持 .txt / .docx 格式") }
  }
}

async function handleReduce() {
  if (!reduceFile.value) { ElMessage.warning("请选择论文文档"); return }
  reducing.value = true; report.value = null
  try {
    const fd = new FormData()
    fd.append("file", reduceFile.value)
    fd.append("max_iterations", String(maxIter.value))
    const { data } = await api.post("/robustness/thesis-reduce/file", fd)
    report.value = data
    if (data.reduction_rate > 0) ElMessage.success(`AI 率降低 ${data.reduction_rate}%`)
  } catch { ElMessage.error("优化失败") }
  finally { reducing.value = false }
}

function copyText() {
  if (report.value?.optimized_text) { navigator.clipboard.writeText(report.value.optimized_text); ElMessage.success("已复制") }
}
function downloadTxt() {
  if (!report.value?.optimized_text) return
  const blob = new Blob([report.value.optimized_text], { type: "text/plain;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a"); a.href = url
  a.download = `AIGC_reduced_${new Date().toISOString().slice(0,10)}.txt`; a.click()
  URL.revokeObjectURL(url); ElMessage.success("已下载")
}
async function downloadPdf() {
  if (!report.value) return
  downloadingPdf.value = true
  try {
    const { data } = await api.post("/robustness/thesis-reduce/pdf", {
      content: report.value.original_text, optimized_text: report.value.optimized_text,
      original_confidence: report.value.original_confidence,
      final_confidence: report.value.final_confidence,
      reduction_rate: report.value.reduction_rate,
      verdict: report.value.verdict,
      changes: report.value.changes || [],
      steps: report.value.steps || [],
      feature_gaps: report.value.feature_gaps || [],
    }, { responseType: "blob" })
    const url = URL.createObjectURL(new Blob([data]))
    const a = document.createElement("a"); a.href = url
    a.download = `AIGC_optimized_${new Date().toISOString().slice(0,10)}.pdf`; a.click()
    URL.revokeObjectURL(url); ElMessage.success("PDF 已下载")
  } catch { ElMessage.error("PDF 生成失败") }
  downloadingPdf.value = false
}
async function downloadDocx() {
  if (!report.value) return
  downloadingDocx.value = true
  try {
    const { data } = await api.post("/robustness/thesis-reduce/docx", {
      content: report.value.original_text, optimized_text: report.value.optimized_text,
      original_confidence: report.value.original_confidence,
      final_confidence: report.value.final_confidence,
      reduction_rate: report.value.reduction_rate,
      verdict: report.value.verdict,
      changes: report.value.changes || [],
      steps: report.value.steps || [],
      feature_gaps: report.value.feature_gaps || [],
    }, { responseType: "blob" })
    const url = URL.createObjectURL(new Blob([data]))
    const a = document.createElement("a"); a.href = url
    a.download = `AIGC_optimized_${new Date().toISOString().slice(0,10)}.docx`; a.click()
    URL.revokeObjectURL(url); ElMessage.success("Word 已下载")
  } catch { ElMessage.error("Word 生成失败") }
  downloadingDocx.value = false
}
</script>

<style scoped>
.reduce-page { max-width: 860px; margin: 0 auto; }
.results { animation: fadeIn .3s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.verdict-card { padding: 16px; }
.change-item { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
.change-item:last-child { border-bottom: none; }
.optimized-text { font-size: 14px; line-height: 2; color: #1a202c; white-space: pre-wrap; }
.report-preview { font-size: 13px; line-height: 1.8; color: #4a5568; white-space: pre-wrap; max-height: 400px; overflow-y: auto; background: #f8fafc; padding: 16px; border-radius: 8px; }
.upload-zone {
  border: 2px dashed #d1d5db; border-radius: 12px; padding: 32px 24px;
  text-align: center; background: #f9fafb; transition: all .25s; cursor: pointer;
}
.upload-zone:hover, .upload-zone.drag-over { border-color: #409eff; background: #ecf5ff; }
.upload-zone.has-file { border-style: solid; border-color: #409eff; background: #f0f7ff; padding: 16px 20px; text-align: left; cursor: default; }
.upload-title { margin: 8px 0 2px; font-size: 14px; color: #4a5568; }
.upload-hint { font-size: 12px; color: #a0aec0; }
.file-card { display: flex; align-items: center; gap: 12px; }
.file-icon-box { width: 44px; height: 44px; border-radius: 8px; background: white; display: flex; align-items: center; justify-content: center; box-shadow: 0 1px 3px rgba(0,0,0,.08); flex-shrink: 0; }
.file-info { flex: 1; min-width: 0; }
.file-name { font-weight: 600; font-size: 14px; color: #1a202c; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-meta { font-size: 12px; color: #a0aec0; margin-top: 2px; }
.feature-gap-item { padding: 10px 0; border-bottom: 1px solid #f1f5f9; }
.feature-gap-item:last-child { border-bottom: none; }
.step-item { padding: 12px 0; border-bottom: 1px solid #f1f5f9; }
.step-item:last-child { border-bottom: none; }
</style>
