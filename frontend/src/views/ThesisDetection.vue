<template>
  <div class="thesis-detect">
    <h1>论文 AIGC 检测</h1>
    <p style="color:#718096;margin-top:0">上传论文文档，生成知网标准检测报告：三色标注 · 疑似原因 · 通过建议</p>

    <!-- 上传区 -->
    <el-card>
      <div class="upload-zone" :class="{ 'is-dragover': dragOver }"
        @dragover.prevent="dragOver=true" @dragleave="dragOver=false" @drop.prevent="handleDrop">
        <el-icon :size="48" color="#a0aec0"><Document /></el-icon>
        <p style="margin:12px 0 4px;font-size:15px;color:#4a5568">
          {{ file ? file.name : '拖拽论文到此处，或点击选择' }}
        </p>
        <p style="font-size:13px;color:#a0aec0">
          {{ file ? (file.size/1024).toFixed(1)+' KB' : '支持 .txt / .docx / .pdf' }}
        </p>
        <input ref="fileInput" type="file" accept=".txt,.docx,.pdf" style="display:none" @change="handleFileInput" />
        <div style="margin-top:12px;display:flex;gap:12px;justify-content:center">
          <el-button @click="triggerUpload">{{ file?'重新选择':'选择文件' }}</el-button>
        </div>
      </div>
      <el-button type="primary" size="large" @click="handleDetect" :loading="detecting" :disabled="!file"
        style="margin-top:12px;width:100%">
        {{ detecting ? '正在逐段分析中...' : '开始检测' }}
      </el-button>
    </el-card>

    <!-- 检测报告 -->
    <div v-if="report" class="report">
      <!-- ① 报告头部 (知网风格) -->
      <el-card class="report-header">
        <div class="header-grid">
          <div><span class="h-label">论文</span><span class="h-val">{{ report.report_meta.filename }}</span></div>
          <div><span class="h-label">检测时间</span><span class="h-val">{{ report.report_meta.detection_time }}</span></div>
          <div><span class="h-label">算法版本</span><span class="h-val">{{ report.report_meta.algorithm_version }}</span></div>
          <div><span class="h-label">自适应阈值</span><span class="h-val" style="color:#63b3ed">{{ report.report_meta.adaptive_threshold?.toFixed(2) || '0.45' }} (自动)</span></div>
          <div><span class="h-label">总字符数</span><span class="h-val">{{ report.overall_score.total_chars }}</span></div>
        </div>
      </el-card>

      <!-- ② 总体评分 + 通过建议 -->
      <div style="display:flex;gap:16px;margin-top:16px">
        <el-card class="score-card" style="flex:1">
          <div class="big-score" :style="{color: scoreColor}">{{ report.overall_score.ai_rate }}%</div>
          <div class="big-label">全文 AI 疑似率</div>
          <div style="margin-top:12px">
            <el-tag :type="report.overall_score.is_ai_generated ? 'danger' : 'success'" size="large">
              {{ report.overall_score.is_ai_generated ? '整体判定: AI 参与生成' : '整体判定: 人类写作为主' }}
            </el-tag>
          </div>
        </el-card>
        <el-card class="verdict-card" style="flex:1"
          :style="{borderLeft: '4px solid ' + (report.recommendation.risk_level==='high'?'#dc2626':report.recommendation.risk_level==='medium'?'#f59e0b':'#10b981')}">
          <div class="verdict-text">{{ report.recommendation.verdict }}</div>
          <p style="color:#718096;font-size:14px;margin-top:8px">{{ report.recommendation.detail }}</p>
          <el-tag :type="report.recommendation.risk_level==='high'?'danger':report.recommendation.risk_level==='medium'?'warning':'success'"
            style="margin-top:8px">
            {{ report.recommendation.risk_level==='high'?'高风险':report.recommendation.risk_level==='medium'?'中风险':'低风险' }}
          </el-tag>
        </el-card>
      </div>

      <!-- 跨章节一致性分析 (V3 核心) -->
      <el-card v-if="report.consistency" style="margin-top:16px" class="consistency-card">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:600">跨章节一致性分析</span>
            <el-tag :type="report.consistency.overall_score > 0.6 ? 'danger' : report.consistency.overall_score > 0.4 ? 'warning' : 'success'" size="small">
              {{ report.consistency.overall_score > 0.6 ? '高度一致 (AI特征)' : report.consistency.overall_score > 0.4 ? '较一致' : '自然波动 (人类特征)' }}
            </el-tag>
          </div>
        </template>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <div>
            <div style="font-size:13px;color:#718096;margin-bottom:2px">风格方差</div>
            <el-progress :percentage="Math.round((1 - report.consistency.style_variance) * 100)" :color="report.consistency.style_variance < 0.2 ? '#dc2626' : '#10b981'" :stroke-width="10" />
            <div style="font-size:11px;color:#a0aec0;margin-top:2px">{{ report.consistency.style_variance < 0.2 ? '各章节风格异常一致' : '各章节风格自然波动' }}</div>
          </div>
          <div>
            <div style="font-size:13px;color:#718096;margin-bottom:2px">章节数</div>
            <div style="font-size:24px;font-weight:700;color:#1a202c">{{ report.consistency.analyzed_count }}/{{ report.consistency.chapter_count }}</div>
          </div>
        </div>
        <el-divider style="margin:12px 0" />
        <div style="font-size:13px;color:#4a5568;line-height:1.8">
          <div>• {{ report.consistency.slop_pattern }}</div>
          <div>• {{ report.consistency.transition_pattern }}</div>
          <div>• {{ report.consistency.sentence_length_pattern }}</div>
        </div>
        <!-- 章节风格对比 -->
        <div v-if="report.consistency.details?.length" style="margin-top:12px">
          <div style="font-size:13px;color:#718096;margin-bottom:8px">章节风格对比</div>
          <div v-for="d in report.consistency.details" :key="d.chapter"
            style="display:flex;align-items:center;gap:8px;padding:6px 10px;margin-bottom:4px;background:#f8fafc;border-radius:6px;font-size:13px">
            <span style="width:60px;color:#718096">{{ d.chapter }}</span>
            <span style="flex:1">句长 {{ d.sent_len_avg }} (CV={{ d.sent_len_cv }})</span>
            <span>Slop {{ d.slop_density }}</span>
            <span style="color:#a0aec0">| {{ d.char_count }}字</span>
          </div>
        </div>
      </el-card>

      <!-- 取证分析: 引用验证 + 数据具体性 -->
      <el-card v-if="report.forensics" style="margin-top:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:600">论文取证分析</span>
            <el-tag :type="report.forensics.overall_risk > 0.5 ? 'danger' : 'success'" size="small">
              综合风险 {{ (report.forensics.overall_risk * 100).toFixed(0) }}%
            </el-tag>
          </div>
        </template>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <!-- 引用验证 -->
          <div v-if="report.forensics.citation" style="padding:12px;background:#f8fafc;border-radius:8px">
            <div style="font-weight:600;font-size:14px;margin-bottom:8px">引用验证</div>
            <div style="font-size:13px;color:#4a5568">
              <div>引用数: {{ report.forensics.citation.total }} (去重: {{ report.forensics.citation.unique }})</div>
              <div>密度: {{ report.forensics.citation.density }}/千字</div>
              <div>泛化比例: {{ (report.forensics.citation.generic_ratio * 100).toFixed(0) }}%</div>
              <div :style="{color: report.forensics.citation.suspicion > 0.5 ? '#dc2626' : '#10b981', marginTop:4, fontWeight:500}">
                {{ report.forensics.citation.pattern }}
              </div>
            </div>
          </div>
          <!-- 数据具体性 -->
          <div style="padding:12px;background:#f8fafc;border-radius:8px">
            <div style="font-weight:600;font-size:14px;margin-bottom:8px">数据具体性</div>
            <div style="font-size:13px;color:#4a5568">
              <div>具体数据: {{ report.forensics.specificity.specific_count }} 处</div>
              <div>模糊描述: {{ report.forensics.specificity.vague_count }} 处</div>
              <div>比值: {{ report.forensics.specificity.ratio.toFixed(1) }}:1</div>
              <div :style="{color: report.forensics.specificity.score < 0.3 ? '#dc2626' : '#10b981', marginTop:4, fontWeight:500}">
                {{ report.forensics.specificity.diagnosis }}
              </div>
            </div>
          </div>
        </div>
        <!-- 风险因素 -->
        <div v-if="report.forensics.risk_factors?.length" style="margin-top:12px">
          <el-alert v-for="(rf,i) in report.forensics.risk_factors" :key="i" type="warning" :title="rf" :closable="false" style="margin-bottom:4px" />
        </div>
        <div v-if="report.forensics.human_indicators?.length" style="margin-top:4px">
          <el-alert v-for="(hi,i) in report.forensics.human_indicators" :key="i" type="success" :title="hi" :closable="false" style="margin-bottom:4px" />
        </div>
      </el-card>

      <!-- ③ 统计摘要 -->
      <el-card style="margin-top:16px">
        <template #header><span style="font-weight:600">检测统计</span></template>
        <div class="stats-row">
          <div class="stat-item"><span class="s-num">{{ report.summary.ai_paragraph_count }}</span><span class="s-lbl">AI 段落</span></div>
          <div class="stat-item"><span class="s-num">{{ report.summary.human_paragraph_count }}</span><span class="s-lbl">人类段落</span></div>
          <div class="stat-item"><span class="s-num">{{ report.summary.high_risk_count }}</span><span class="s-lbl">高风险</span></div>
          <div class="stat-item"><span class="s-num">{{ report.summary.medium_risk_count }}</span><span class="s-lbl">中风险</span></div>
          <div class="stat-item"><span class="s-num">{{ report.summary.low_risk_count }}</span><span class="s-lbl">低风险</span></div>
          <div class="stat-item"><span class="s-num" style="color:#718096">{{ report.paragraphs?.filter((p:any)=>p.is_reference)?.length || 0 }}</span><span class="s-lbl">参考文献</span></div>
        </div>
      </el-card>

      <!-- ④ 逐段分析 (三色标注 + 疑似原因) -->
      <el-card style="margin-top:16px">
        <template #header>
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:600">逐段分析报告</span>
            <div class="legend">
              <span class="legend-dot" style="background:#dc2626"></span>高(≥70%)
              <span class="legend-dot" style="background:#f59e0b"></span>中(40-70%)
              <span class="legend-dot" style="background:#10b981"></span>低(<40%)
            </div>
          </div>
        </template>

        <div class="para-list">
          <div v-for="p in report.paragraphs" :key="p.index" class="para-card"
            :style="{borderLeftColor: suspicionColor(p.suspicion), background: suspicionBg(p.suspicion)}">
            <div class="para-top">
              <el-tag v-if="p.is_reference" type="info" size="small">
                <el-icon><Collection /></el-icon> 引用
              </el-tag>
              <el-tag v-else :type="p.level==='high'?'danger':p.level==='medium'?'warning':'success'" size="small">
                {{ p.level==='high'?'高风险':p.level==='medium'?'中风险':'低风险' }}
              </el-tag>
              <span class="para-pct" :style="{color: suspicionColor(p.suspicion)}">{{ p.suspicion.toFixed(0) }}%</span>
              <span style="font-size:12px;color:#a0aec0">{{ p.length }} 字</span>
              <span v-if="p.section" style="font-size:12px;color:#a0aec0">|</span>
              <span v-if="p.section" style="font-size:12px;color:#718096;font-weight:500">{{ p.section }}</span>
              <span style="font-size:12px;color:#a0aec0">|</span>
              <span style="font-size:13px;color:#718096;margin-left:4px">原因:</span>
              <el-tag v-for="r in p.reasons" :key="r" size="small" type="info" style="margin-left:2px">{{ r }}</el-tag>
            </div>
            <div class="para-body">{{ p.text }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 近期检测结果 -->
    <div v-if="cachedResults.length > 0" style="margin-top:24px">
      <h3 style="margin-bottom:12px">近期检测结果</h3>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div v-for="r in cachedResults" :key="r.id"
          style="display:flex;align-items:center;justify-content:space-between;padding:10px 16px;background:white;border-radius:8px;border:1px solid #e2e8f0;cursor:pointer"
          @click="report = r.data; scrollToTop()">
          <div>
            <span style="font-weight:500">{{ r.title }}</span>
            <span style="font-size:12px;color:#a0aec0;margin-left:8px">{{ r.timestamp }}</span>
          </div>
          <div style="display:flex;align-items:center;gap:12px">
            <span style="font-size:13px;color:#718096">AI率 {{ r.data?.overall_score?.ai_rate || '?' }}%</span>
            <el-tag :type="r.data?.overall_score?.is_ai_generated ? 'danger' : 'success'" size="small">
              {{ r.data?.overall_score?.is_ai_generated ? 'AI' : '人' }}
            </el-tag>
            <el-button size="small" text type="danger" @click.stop="resultsStore.remove(r.id)">×</el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { Document } from "@element-plus/icons-vue"
import { useResultsStore } from "@/stores/results"
import { usePollTask } from "@/composables/usePollTask"
import { extractApiErrorMessage } from "@/utils/errors"

const file = ref<File | null>(null)
const detecting = ref(false)
const report = ref<any>(null)
const dragOver = ref(false)
const fileInput = ref<HTMLInputElement>()
const resultsStore = useResultsStore()
const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })
const cachedResults = computed(() => resultsStore.getLatest("thesis").reverse())
const scoreColor = computed(() => {
  if (!report.value) return "#718096"
  const r = report.value.overall_score.ai_rate
  return r >= 30 ? "#dc2626" : r >= 15 ? "#f59e0b" : "#10b981"
})

function suspicionColor(pct: number): string {
  if (pct >= 70) return "#dc2626"
  if (pct >= 40) return "#f59e0b"
  return "#10b981"
}

function suspicionBg(pct: number): string {
  if (pct >= 70) return "rgba(220,38,38,0.06)"
  if (pct >= 40) return "rgba(245,158,11,0.04)"
  return "rgba(16,185,129,0.02)"
}

function triggerUpload() { fileInput.value?.click() }
function handleFileInput(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files?.length) { file.value = t.files[0]; report.value = null }
}
function handleDrop(e: DragEvent) {
  dragOver.value = false
  if (e.dataTransfer?.files?.length) { file.value = e.dataTransfer.files[0]; report.value = null }
}

const { pollTask: pollThesis } = usePollTask()

async function handleDetect() {
  if (!file.value) return
  detecting.value = true; report.value = null
  try {
    const fd = new FormData(); fd.append("file", file.value)
    const { data } = await api.post("/detect/thesis", fd, {
      timeout: 30000,
    })
    if (data.task_id) {
      ElMessage.success("论文检测任务已提交: " + data.task_id)
      await pollThesis(
        data.task_id,
        (resultData: any) => {
          report.value = resultData
          resultsStore.add("thesis", file.value?.name || "论文", resultData)
        },
        (errMsg: string) => {
          ElMessage.error(errMsg)
        },
      )
    } else if (data.overall_score) {
      report.value = data
      resultsStore.add("thesis", file.value?.name || "论文", data)
    } else {
      ElMessage.error(data.message || "论文检测失败")
    }
  } catch (e: any) {
    ElMessage.error(extractApiErrorMessage(e, "论文检测失败"))
  } finally {
    detecting.value = false
  }
}
</script>

<style scoped>
.thesis-detect { max-width: 900px; margin: 0 auto; }
.upload-zone { border: 2px dashed #d1d5db; border-radius: 12px; padding: 36px; text-align: center; background: #f9fafb; transition: all .3s; }
.upload-zone:hover, .upload-zone.is-dragover { border-color: #409eff; background: #ecf5ff; }

.report { animation: fadeIn .5s ease; margin-top: 20px; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }

.report-header { background: linear-gradient(135deg, #1a1a2e, #2d3748); color: #e2e8f0; }
.header-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.h-label { font-size: 12px; color: #718096; display: block; }
.h-val { font-size: 14px; color: #e2e8f0; }

.score-card, .verdict-card { text-align: center; padding: 16px; }
.big-score { font-size: 48px; font-weight: 800; }
.big-label { font-size: 14px; color: #718096; margin-top: 4px; }
.verdict-text { font-size: 22px; font-weight: 700; color: #1a202c; }

.stats-row { display: flex; justify-content: space-around; }
.stat-item { text-align: center; }
.s-num { display: block; font-size: 28px; font-weight: 700; color: #1a202c; }
.s-lbl { display: block; font-size: 12px; color: #718096; margin-top: 2px; }

.legend { display: flex; align-items: center; gap: 12px; font-size: 12px; color: #718096; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 4px; }

.para-list { display: flex; flex-direction: column; gap: 10px; }
.para-card { border-left: 4px solid #10b981; padding: 12px 14px; border-radius: 0 8px 8px 0; transition: all .2s; }
.para-card:has(.el-tag--info) { border-left-color: #a0aec0; }
.para-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.para-top { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.para-pct { font-weight: 700; font-size: 15px; }
.para-body { font-size: 14px; line-height: 1.8; color: #4a5568; }
</style>
