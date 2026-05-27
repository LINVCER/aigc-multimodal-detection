<template>
  <div>
    <div style="display:flex;align-items:center;justify-content:space-between">
      <h1>文本检测</h1>
      <div v-if="modelInfo" style="display:flex;align-items:center;gap:8px;font-size:13px;color:#718096">
        <el-tag size="small" type="info">模型 v2</el-tag>
        <span>F1: {{ modelInfo.val_f1 ? (modelInfo.val_f1 * 100).toFixed(1) + '%' : 'N/A' }}</span>
        <el-tag size="small" :type="modelInfo.calibration === 'disabled' ? 'warning' : 'success'">
          {{ modelInfo.calibration === 'disabled' ? '原始logits' : '已校准' }}
        </el-tag>
        <el-tag size="small" :type="modelInfo.llm_api?.enabled ? 'success' : 'info'">
          {{ modelInfo.llm_api?.enabled ? 'DeepSeek ✓' : 'API 未启用' }}
        </el-tag>
        <el-button size="small" text @click="refreshModelInfo">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <el-card>
      <el-input
        v-model="content"
        type="textarea"
        :rows="8"
        placeholder="请输入或粘贴需要检测的文本内容... (支持最多 50000 字符)"
        maxlength="50000"
        show-word-limit
      />
      <div style="margin-top:16px;display:flex;align-items:center;gap:12px">
        <el-button type="primary" @click="handleDetect" :loading="detecting">
          <el-icon><Search /></el-icon> 开始检测
        </el-button>
        <el-checkbox v-model="options.explain">生成解释报告</el-checkbox>
        <el-checkbox v-model="options.attribution">模型溯源</el-checkbox>
      </div>
    </el-card>

    <!-- 结果卡片 -->
    <el-card v-if="result" style="margin-top:20px" header="检测结果">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="判定结果">
          <el-tag :type="result.is_ai_generated ? 'danger' : 'success'" size="large">
            {{ result.is_ai_generated ? 'AI 生成' : '人类写作' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="置信度">{{ (result.confidence * 100).toFixed(1) }}%</el-descriptions-item>
        <el-descriptions-item label="校准置信度" v-if="result.calibrated_confidence">
          {{ (result.calibrated_confidence * 100).toFixed(1) }}%
        </el-descriptions-item>
        <el-descriptions-item label="风险等级">
          <el-tag :type="riskTagTypeComputed">{{ result.risk_level || 'N/A' }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="result.arbitration_warning" style="margin-top:12px">
        <el-alert type="warning" :title="result.arbitration_warning" show-icon />
      </div>

      <!-- 分段检测结果 -->
      <div v-if="result.chunk_details?.length" style="margin-top:16px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
          <span style="font-weight:600;font-size:14px">分段检测 ({{ result.chunk_details.length }} 段)</span>
          <div style="display:flex;align-items:center;gap:12px;font-size:12px;color:#a0aec0">
            <span><span style="color:#dc2626">■</span> 高(≥70%)</span>
            <span><span style="color:#f59e0b">■</span> 中(30-70%)</span>
            <span><span style="color:#10b981">■</span> 低(&lt;30%)</span>
          </div>
        </div>
        <div style="max-height:360px;overflow-y:auto;border:1px solid #e2e8f0;border-radius:8px">
          <div v-for="chunk in result.chunk_details" :key="chunk.index"
            :style="{
              display:'flex',alignItems:'center',gap:'10px',padding:'8px 14px',
              borderBottom:'1px solid #f1f5f9',
              borderLeft:'4px solid ' + chunkColor(chunk.score),
              background: chunkBg(chunk.score),
            }">
            <span style="font-size:11px;color:#a0aec0;flex-shrink:0;width:32px">#{{ chunk.index + 1 }}</span>
            <span style="flex:1;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#4a5568">
              {{ chunk.text_preview }}
            </span>
            <el-progress
              :percentage="Math.round(chunk.score * 100)"
              :color="chunkColor(chunk.score)"
              :stroke-width="8"
              style="width:100px;flex-shrink:0"
            />
            <el-tag :type="chunk.level==='high'?'danger':chunk.level==='medium'?'warning':'success'" size="small" style="flex-shrink:0">
              {{ chunk.level==='high'?'高':chunk.level==='medium'?'中':'低' }}
            </el-tag>
          </div>
        </div>
      </div>

      <TextHighlight
        v-if="highlightSegments.length"
        :text="content"
        :segments="highlightSegments"
        style="margin-top:16px"
      />
    </el-card>

    <div v-if="cachedResults.length > 0" style="margin-top:16px">
      <h3 style="margin-bottom:8px;font-size:14px;color:#718096">近期检测</h3>
      <div v-for="r in cachedResults" :key="r.id"
        style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:white;border-radius:6px;border:1px solid #e2e8f0;margin-bottom:4px;cursor:pointer"
        @click="result=r.data;scrollToTop()">
        <span style="font-size:13px;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.title }}</span>
        <div style="display:flex;align-items:center;gap:8px;flex-shrink:0">
          <span style="font-size:12px;color:#a0aec0">{{ r.timestamp }}</span>
          <el-tag :type="r.data?.is_ai_generated?'danger':'success'" size="small">
            {{ r.data?.is_ai_generated?'AI':'人' }} {{ r.data?.confidence ? (r.data.confidence*100).toFixed(0)+'%' : '?' }}
          </el-tag>
          <el-button size="small" text type="danger" @click.stop="resultsStore.remove(r.id)">x</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { Search, Refresh } from "@element-plus/icons-vue"
import { useResultsStore } from "@/stores/results"
import { usePollTask } from "@/composables/usePollTask"
import { extractApiErrorMessage } from "@/utils/errors"
import TextHighlight from "@/components/text/TextHighlight.vue"
import { confidenceColor, confidenceBgColor, riskTagType } from "@/utils/color"
import { formatConfidence } from "@/utils/format"

const content = ref("")
const detecting = ref(false)
const result = ref<any>(null)
const modelInfo = ref<any>(null)
const resultsStore = useResultsStore()
const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })
const { pollTask: pollTaskAsync } = usePollTask()
const cachedResults = computed(() => resultsStore.getLatest("text").reverse())
const options = reactive({ explain: true, attribution: true })

const highlightSegments = computed(() => {
  if (!result.value?.explanation?.suspicious_spans?.length) return []
  const spans = result.value.explanation.suspicious_spans
  const text = content.value
  const segments: { text: string; score?: number; reasons?: string[] }[] = []
  let lastEnd = 0
  for (const span of spans) {
    const start = span.start ?? 0
    const end = span.end ?? 0
    if (start > lastEnd) {
      segments.push({ text: text.slice(lastEnd, start) })
    }
    if (start < end && start >= lastEnd) {
      segments.push({
        text: text.slice(start, end),
        score: span.score ?? result.value.confidence,
        reasons: [span.detail || span.reason || '可疑 AI 标志'],
      })
      lastEnd = end
    }
  }
  if (lastEnd < text.length) {
    segments.push({ text: text.slice(lastEnd) })
  }
  return segments
})

function preprocess(text: string): string {
  // 默认开启：去引用标记、去多余空格空行
  text = text.replace(/\[\d+(?:[,，\s]*\d+)*\]/g, '')
  text = text.replace(/\[\d+[-–—]\d+\]/g, '')
  text = text.replace(/\n{3,}/g, '\n\n')
  text = text.trim()
  return text
}

async function refreshModelInfo() {
  try {
    const { data } = await api.get("/system/model-info")
    modelInfo.value = data
  } catch {
    // Non-critical: model info is decorative
    console.warn("[TextDetection] Failed to fetch model info")
  }
}

onMounted(() => refreshModelInfo())

// 使用公共颜色函数
const chunkColor = confidenceColor
const chunkBg = confidenceBgColor

const riskTagTypeComputed = computed(() => {
  if (!result.value?.risk_level) return "info"
  return riskTagType(result.value.risk_level)
})

async function handleDetect() {
  if (!content.value.trim()) { ElMessage.warning("请输入文本内容"); return }
  const cleaned = preprocess(content.value)
  detecting.value = true
  try {
    const { data } = await api.post("/detect/text", {
      content: cleaned,
      options,
    })
    if (data.status === "completed") {
      result.value = data
      resultsStore.add("text", content.value.slice(0, 40), data)
    } else if (data.status === "processing") {
      ElMessage.success("检测任务已提交: " + data.task_id)
      await pollTask(data.task_id)
    } else if (data.status === "failed") {
      ElMessage.error(data.message || "检测失败")
    } else {
      ElMessage.warning("未知状态: " + data.status)
    }
  } catch (e: any) {
    ElMessage.error(extractApiErrorMessage(e, "检测失败"))
  } finally {
    detecting.value = false
  }
}

async function pollTask(taskId: string) {
  await pollTaskAsync(taskId,
    (resultData) => {
      result.value = resultData
      resultsStore.add("text", content.value.slice(0, 40), resultData)
    },
    (errMsg) => {
      ElMessage.error(errMsg)
    }
  )
}
</script>
