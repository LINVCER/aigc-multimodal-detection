<template>
  <div class="batch-detect">
    <div style="display:flex;align-items:center;justify-content:space-between">
      <h1>批量检测</h1>
      <el-button @click="openHistory" text>
        <el-icon><Clock /></el-icon> 历史记录
      </el-button>
    </div>

    <!-- 上传区 -->
    <el-card>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        multiple
        drag
        accept=".txt,.docx,.pdf"
        :on-change="handleFilesChange"
        :limit="100"
        :on-exceed="() => ElMessage.warning('单次最多 100 个文件')"
      >
        <el-icon :size="40"><UploadFilled /></el-icon>
        <div class="upload-text">拖拽文件到此处 或 <em>点击选择</em></div>
        <template #tip>
          <div class="upload-tip">支持 .txt / .docx / .pdf，单文件 ≤10MB，最多 100 个</div>
        </template>
      </el-upload>

      <div v-if="files.length" style="margin-top:12px">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
          <span style="font-size:13px;color:#718096">已选 {{ files.length }} 个文件</span>
          <el-button size="small" text @click="files=[];uploadRef?.clearFiles()">清空</el-button>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          <el-tag v-for="(f,i) in files" :key="i" closable @close="removeFile(i)" size="small">
            {{ f.name }} ({{ formatSize(f.size) }})
          </el-tag>
        </div>
      </div>

      <div style="margin-top:16px;display:flex;gap:12px;align-items:center">
        <el-button type="primary" @click="startBatch" :loading="submitting" :disabled="!files.length">
          <el-icon><VideoPlay /></el-icon> 开始检测 ({{ files.length }} 份)
        </el-button>
        <el-button v-if="batchRunning" type="danger" @click="cancelBatch" :loading="cancelling">
          <el-icon><Close /></el-icon> 取消
        </el-button>
        <el-button v-if="results.length && !batchRunning" @click="exportCSV">CSV</el-button>
        <el-button v-if="results.length && !batchRunning" @click="exportJSON">JSON</el-button>
        <el-popconfirm title="确定清空当前结果？" @confirm="resetAll">
          <el-button v-if="results.length && !batchRunning" type="danger" text>清空</el-button>
        </el-popconfirm>
      </div>
    </el-card>

    <!-- 进度 -->
    <el-card v-if="batchId" style="margin-top:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600">检测进度</span>
          <el-tag :type="batchStatusTag" size="small">{{ batchStatusText }}</el-tag>
        </div>
      </template>
      <el-progress :percentage="progressPct" :status="batchStatus === 'completed' ? 'success' : batchStatus === 'cancelled' ? 'exception' : undefined" :stroke-width="18" :text-inside="true" />
      <div style="margin-top:12px;display:flex;justify-content:space-between;font-size:13px;color:#718096">
        <span>已完成 {{ completedCount }} / {{ totalCount }} 份</span>
        <span v-if="batchRunning">并行数: 4 · {{ estimatedRemaining }}</span>
        <span v-else-if="durationSec">总耗时: {{ durationText }}</span>
      </div>
    </el-card>

    <!-- 汇总统计 -->
    <el-row v-if="batchSummary" :gutter="16" style="margin-top:16px">
      <el-col :span="6" v-for="s in summaryCards" :key="s.label">
        <el-card shadow="hover" :style="{textAlign:'center',borderLeft:'3px solid '+s.color}">
          <div :style="{fontSize:'28px',fontWeight:700,color:s.color}">{{ s.value }}</div>
          <div style="font-size:13px;color:#718096;margin-top:4px">{{ s.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分布条 -->
    <el-card v-if="batchSummary" style="margin-top:16px">
      <template #header><span style="font-weight:600">风险分布</span></template>
      <div style="display:flex;height:28px;border-radius:6px;overflow:hidden;margin-bottom:8px">
        <div v-if="batchSummary.high_risk > 0" :style="{width: batchSummary.high_risk/batchSummary.completed*100+'%', background:'#dc2626'}" />
        <div v-if="batchSummary.medium_risk > 0" :style="{width: batchSummary.medium_risk/batchSummary.completed*100+'%', background:'#f59e0b'}" />
        <div v-if="batchSummary.low_risk > 0" :style="{width: batchSummary.low_risk/batchSummary.completed*100+'%', background:'#10b981'}" />
      </div>
      <div style="display:flex;justify-content:space-around;font-size:13px;color:#718096">
        <span><span style="color:#dc2626">&#9632;</span> 高风险 (≥70%) {{ batchSummary.high_risk }}</span>
        <span><span style="color:#f59e0b">&#9632;</span> 中风险 (30-70%) {{ batchSummary.medium_risk }}</span>
        <span><span style="color:#10b981">&#9632;</span> 低风险 (&lt;30%) {{ batchSummary.low_risk }}</span>
      </div>
    </el-card>

    <!-- 结果表格 -->
    <el-card v-if="results.length" style="margin-top:16px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600">检测结果 ({{ results.length }})</span>
          <div style="display:flex;gap:8px">
            <el-input v-model="searchKeyword" placeholder="搜索文件名..." size="small" style="width:200px" clearable />
            <el-select v-model="filterRisk" placeholder="风险筛选" size="small" style="width:110px" clearable>
              <el-option label="高风险" value="high" />
              <el-option label="中风险" value="medium" />
              <el-option label="低风险" value="low" />
              <el-option label="失败" value="error" />
            </el-select>
            <el-select v-model="sortBy" size="small" style="width:120px">
              <el-option label="默认顺序" value="index" />
              <el-option label="AI 率 高→低" value="conf-desc" />
              <el-option label="AI 率 低→高" value="conf-asc" />
              <el-option label="文件名 A→Z" value="name" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table :data="filteredResults" stripe border max-height="600" style="width:100%">
        <el-table-column type="index" label="#" width="50" />
        <el-table-column prop="filename" label="文件名" min-width="220" show-overflow-tooltip />
        <el-table-column label="AI 率" width="160" sortable :sort-method="(a: any, b: any) => a.confidence - b.confidence">
          <template #default="{row}">
            <div v-if="row.error" style="color:#dc2626;font-size:12px">{{ row.error }}</div>
            <el-progress v-else :percentage="Math.round(row.confidence*100)" :color="confColor(row.confidence)" :stroke-width="12">
              <span style="font-size:11px">{{ (row.confidence*100).toFixed(0) }}%</span>
            </el-progress>
          </template>
        </el-table-column>
        <el-table-column label="判定" width="90">
          <template #default="{row}">
            <el-tag v-if="row.error" type="danger" size="small">失败</el-tag>
            <el-tag v-else :type="row.is_ai_generated ? 'danger' : 'success'" size="small">
              {{ row.is_ai_generated ? 'AI' : '人' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="80">
          <template #default="{row}">
            <el-tag v-if="row.risk_level" :type="riskTag(row.risk_level)" size="small">
              {{ riskLabel(row.risk_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="字数" width="80" prop="char_count" />
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{row}">
            <el-button v-if="!row.error" size="small" link @click="viewDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="检测详情" width="640px">
      <el-descriptions v-if="detailRow" :column="2" border>
        <el-descriptions-item label="文件名">{{ detailRow.filename }}</el-descriptions-item>
        <el-descriptions-item label="AI 率">{{ (detailRow.confidence*100).toFixed(1) }}%</el-descriptions-item>
        <el-descriptions-item label="判定">
          <el-tag :type="detailRow.is_ai_generated ? 'danger' : 'success'" size="small">
            {{ detailRow.is_ai_generated ? 'AI 生成' : '人类写作' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="风险等级">
          <el-tag :type="riskTag(detailRow.risk_level)" size="small">{{ riskLabel(detailRow.risk_level) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="字符数">{{ detailRow.char_count || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="任务ID">{{ detailRow.task_id || 'N/A' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <!-- 历史记录抽屉 -->
    <el-drawer v-model="showHistory" title="批量检测历史" size="420px">
      <div v-if="!history.length" style="text-align:center;color:#a0aec0;margin-top:40px">
        <el-empty description="暂无历史记录" />
      </div>
      <div v-for="b in history" :key="b.batch_id" style="padding:12px;margin-bottom:8px;border:1px solid #e2e8f0;border-radius:8px;cursor:pointer"
        @click="loadHistoryBatch(b.batch_id);showHistory=false">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600;font-size:14px">{{ b.total }} 份文件</span>
          <el-tag :type="b.status==='completed'?'success':b.status==='cancelled'?'info':'warning'" size="small">
            {{ ({completed:'完成',cancelled:'已取消',processing:'进行中',partial:'部分完成'} as Record<string,string>)[b.status] || b.status }}
          </el-tag>
        </div>
        <div style="font-size:12px;color:#a0aec0;margin-top:6px">
          AI {{ b.ai_count }}/{{ b.completed }} · {{ b.created_at?.slice(0,19) || '' }}
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { UploadFilled, VideoPlay, Close, Clock } from "@element-plus/icons-vue"
import { confidenceColor, riskTagType } from "@/utils/color"
import { formatSize } from "@/utils/format"

interface FileItem { name: string; size: number; raw: File }
interface ResultItem {
  index: number; filename: string; confidence: number
  is_ai_generated: boolean; risk_level: string
  char_count?: number; task_id?: string; error?: string
}

// 上传状态
const files = ref<FileItem[]>([])
const uploadRef = ref<any>(null)
const submitting = ref(false)

// 批处理状态
const batchId = ref("")
const batchStatus = ref("")
const totalCount = ref(0)
const completedCount = ref(0)
const results = ref<ResultItem[]>([])
const startTime = ref(0)
const durationSec = ref(0)
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const cancelling = ref(false)

// 筛选状态
const searchKeyword = ref("")
const filterRisk = ref("")
const sortBy = ref("index")
const detailVisible = ref(false)
const detailRow = ref<ResultItem | null>(null)
const showHistory = ref(false)
const history = ref<any[]>([])

// 计算属性
const batchRunning = computed(() => batchStatus.value === "processing" || batchStatus.value === "pending")
const progressPct = computed(() => totalCount.value ? Math.round(completedCount.value / totalCount.value * 100) : 0)
const batchStatusTag = computed(() => {
  const m: Record<string,string> = { completed: "success", processing: "warning", cancelled: "info", partial: "warning" }
  return m[batchStatus.value] || "info"
})
const batchStatusText = computed(() => {
  const m: Record<string,string> = { completed: "已完成", processing: "处理中...", cancelled: "已取消", partial: "部分完成", pending: "排队中" }
  return m[batchStatus.value] || batchStatus.value
})
const estimatedRemaining = computed(() => {
  if (!startTime.value || completedCount.value < 1) return "计算中..."
  const elapsed = (Date.now() - startTime.value) / 1000
  const perItem = elapsed / completedCount.value
  const rem = (totalCount.value - completedCount.value) * perItem
  return rem < 60 ? `约${Math.round(rem)}秒` : `约${Math.round(rem/60)}分钟`
})
const durationText = computed(() => {
  const s = durationSec.value
  if (s < 60) return `${s}秒`
  if (s < 3600) return `${Math.floor(s/60)}分${s%60}秒`
  return `${Math.floor(s/3600)}时${Math.floor(s%3600/60)}分`
})

const batchSummary = computed(() => {
  const valid = results.value.filter(r => "confidence" in r)
  if (!valid.length) return null
  return {
    completed: valid.length,
    ai_count: valid.filter(r => r.is_ai_generated).length,
    human_count: valid.filter(r => !r.is_ai_generated).length,
    high_risk: valid.filter(r => r.risk_level === "high").length,
    medium_risk: valid.filter(r => r.risk_level === "medium").length,
    low_risk: valid.filter(r => r.risk_level === "low").length,
    errors: results.value.filter(r => r.error).length,
    avg_conf: valid.reduce((s,r) => s + r.confidence, 0) / valid.length,
  }
})

const summaryCards = computed(() => {
  const s = batchSummary.value
  if (!s) return []
  return [
    { label: "AI 检出", value: s.ai_count, color: "#dc2626" },
    { label: "人类写作", value: s.human_count, color: "#10b981" },
    { label: "平均 AI 率", value: (s.avg_conf * 100).toFixed(1) + "%", color: "#f59e0b" },
    { label: "失败", value: s.errors, color: "#6b7280" },
  ]
})

const filteredResults = computed(() => {
  let list = [...results.value]
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    list = list.filter(r => r.filename.toLowerCase().includes(kw))
  }
  if (filterRisk.value === "error") {
    list = list.filter(r => r.error)
  } else if (filterRisk.value) {
    list = list.filter(r => r.risk_level === filterRisk.value)
  }
  switch (sortBy.value) {
    case "conf-desc": list.sort((a,b) => (b.confidence||0) - (a.confidence||0)); break
    case "conf-asc": list.sort((a,b) => (a.confidence||0) - (b.confidence||0)); break
    case "name": list.sort((a,b) => a.filename.localeCompare(b.filename)); break
    default: list.sort((a,b) => (a.index||0) - (b.index||0))
  }
  return list
})

// 使用公共工具函数
const confColor = confidenceColor
const riskTag = riskTagType
function riskLabel(level: string): string {
  const m: Record<string,string> = { high: "高", medium: "中", low: "低" }
  return m[level] || level
}

// 文件操作
function handleFilesChange(uploadFile: any) {
  files.value.push({ name: uploadFile.name, size: uploadFile.size || 0, raw: uploadFile.raw })
}
function removeFile(i: number) {
  files.value.splice(i, 1)
  uploadRef.value?.handleRemove(uploadRef.value.uploadFiles[i])
}

// 批量检测
async function startBatch() {
  if (!files.value.length) { ElMessage.warning("请选择文件"); return }
  submitting.value = true
  try {
    const fd = new FormData()
    for (const f of files.value) fd.append("files", f.raw)
    const { data } = await api.post("/detect/batch", fd, {
      timeout: 30000,
    })
    batchId.value = data.batch_id
    totalCount.value = data.total
    batchStatus.value = "processing"
    completedCount.value = 0
    results.value = []
    startTime.value = Date.now()
    startPolling()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || "提交失败")
  }
  submitting.value = false
}

function startPolling() {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(pollProgress, 800)
}

async function pollProgress() {
  if (!batchId.value) return
  try {
    const { data } = await api.get(`/detect/batch/${batchId.value}/progress`)
    batchStatus.value = data.status
    completedCount.value = data.completed
    if (data.results?.length) results.value = data.results
    if (data.status === "completed" || data.status === "cancelled") {
      stopPolling()
      durationSec.value = Math.round((Date.now() - startTime.value) / 1000)
      const ai = results.value.filter(r => r.is_ai_generated).length
      ElMessage.success(`完成: ${data.completed} 份, AI 检出 ${ai} 份`)
    }
  } catch { /* ignore */ }
}

function stopPolling() {
  if (pollTimer.value) { clearInterval(pollTimer.value); pollTimer.value = null }
}

async function cancelBatch() {
  cancelling.value = true
  try {
    await api.post(`/detect/batch/${batchId.value}/cancel`)
    ElMessage.warning("已取消")
  } catch { /* ignore */ }
  cancelling.value = false
}

function resetAll() {
  stopPolling()
  batchId.value = ""; batchStatus.value = ""; results.value = []
  totalCount.value = 0; completedCount.value = 0; durationSec.value = 0
}

function viewDetail(row: ResultItem) { detailRow.value = row; detailVisible.value = true }

// 历史
function openHistory() {
  showHistory.value = true
  loadHistory()
}
async function loadHistory() {
  try {
    const { data } = await api.get("/detect/batch/history")
    history.value = data.batches || []
  } catch { /* ignore */ }
}

async function loadHistoryBatch(bid: string) {
  stopPolling()
  try {
    const { data } = await api.get(`/detect/batch/${bid}/report`)
    batchId.value = data.batch_id
    batchStatus.value = data.status
    totalCount.value = data.summary.total
    completedCount.value = data.summary.completed
    results.value = data.results || []
    durationSec.value = 0
    ElMessage.success("已加载历史批次")
  } catch { /* ignore */ }
}

// 导出
function exportCSV() {
  const hdr = "序号,文件名,AI率(%),判定,风险等级,字符数\n"
  const rows = results.value.map((r,i) =>
    `${i+1},${r.filename},${((r.confidence||0)*100).toFixed(1)},${r.error?'失败':(r.is_ai_generated?'AI':'人')},${r.risk_level||'-'},${r.char_count||'-'}`
  ).join("\n")
  downloadBlob("﻿" + hdr + rows, `AIGC_batch_${new Date().toISOString().slice(0,10)}.csv`, "text/csv;charset=utf-8")
}

function exportJSON() {
  const report = {
    exported_at: new Date().toISOString(),
    batch_id: batchId.value,
    total: totalCount.value,
    summary: batchSummary.value,
    results: results.value,
  }
  downloadBlob(JSON.stringify(report, null, 2), `AIGC_batch_${batchId.value}.json`, "application/json")
}

function downloadBlob(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出: ${filename}`)
}

onUnmounted(() => stopPolling())
</script>

<style scoped>
.batch-detect h1 { margin-bottom: 20px; }
.upload-text { margin-top: 8px; font-size: 15px; color: #4a5568; }
.upload-text em { color: #409eff; font-style: normal; font-weight: 600; }
.upload-tip { font-size: 12px; color: #a0aec0; margin-top: 8px; }
</style>
