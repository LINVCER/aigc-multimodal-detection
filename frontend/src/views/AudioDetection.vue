<template>
  <div class="audio-detect">
    <h1>音频检测</h1>
    <p style="color:#718096;margin-top:0">检测语音是否为 AI 合成 — 三路融合: Wav2Vec2 + Resemble + RawNet2</p>

    <el-card>
      <div class="upload-zone" :class="{ 'has-file': file }" @click="triggerUpload" @dragover.prevent @drop.prevent="handleDrop">
        <div v-if="!file">
          <el-icon :size="48" color="#a0aec0"><Microphone /></el-icon>
          <p style="margin:12px 0 4px;font-size:15px;color:#4a5568">拖拽音频文件到此处，或点击选择</p>
          <p style="font-size:13px;color:#a0aec0">支持 .wav / .mp3 / .flac / .m4a</p>
        </div>
        <div v-else class="file-preview">
          <div style="display:flex;align-items:center;gap:12px">
            <el-icon :size="32" color="#409eff"><VideoPause /></el-icon>
            <div>
              <div style="font-weight:600;font-size:15px">{{ file.name }}</div>
              <div style="font-size:13px;color:#a0aec0">{{ formatSize(file.size) }}</div>
            </div>
            <el-button size="small" text type="danger" @click.stop="file=null" style="margin-left:auto">移除</el-button>
          </div>
          <!-- 音频播放 -->
          <audio v-if="audioUrl" :src="audioUrl" controls style="width:100%;margin-top:12px;height:40px" />
        </div>
        <input ref="fileInput" type="file" accept="audio/*" style="display:none" @change="handleFileInput" />
      </div>

      <el-button type="primary" size="large" @click="handleDetect" :loading="detecting" :disabled="!file" style="margin-top:16px;width:100%">
        <el-icon><Search /></el-icon> {{ detecting ? '检测中...' : '开始检测' }}
      </el-button>
    </el-card>

    <!-- 结果卡片 -->
    <div v-if="result" class="result-section">
      <div style="display:flex;gap:16px;margin-top:16px">
        <!-- 主判定 -->
        <el-card class="verdict-card" style="flex:1" :style="{borderLeft:'4px solid '+verdictColor}">
          <div class="verdict-icon">
            <el-icon :size="48" :color="verdictColor">
              <CircleCheck v-if="!result.is_ai_generated" />
              <WarningFilled v-else />
            </el-icon>
          </div>
          <div class="verdict-text" :style="{color:verdictColor}">
            {{ result.is_ai_generated ? 'AI 合成语音' : '真实人类语音' }}
          </div>
          <el-tag :type="result.is_ai_generated ? 'danger' : 'success'" size="large" style="margin-top:8px">
            置信度 {{ (result.confidence * 100).toFixed(1) }}%
          </el-tag>
        </el-card>

        <!-- 置信度仪表盘 -->
        <el-card class="score-card" style="flex:1;text-align:center">
          <ConfidenceGauge :value="result.confidence" label="综合置信度" />
          <div style="margin-top:8px">
            <el-tag :type="riskTagTypeComputed" size="small">{{ result.risk_level || 'N/A' }}</el-tag>
          </div>
        </el-card>
      </div>

      <!-- 三路分支 -->
      <el-card v-if="branches.length" style="margin-top:16px">
        <template #header><span style="font-weight:600">检测分支详情</span></template>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
          <div v-for="b in branches" :key="b.name" class="branch-card">
            <div style="font-weight:600;font-size:14px;margin-bottom:6px">{{ branchLabel(b.name) }}</div>
            <el-progress :percentage="Math.round(b.confidence * 100)" :color="confColor(b.confidence)" :stroke-width="8" />
            <div style="font-size:12px;color:#a0aec0;margin-top:4px">权重: {{ (b.weight * 100).toFixed(0) }}%</div>
            <el-tag v-if="b.confidence > 0.3" type="danger" size="small" style="margin-top:4px">AI</el-tag>
            <el-tag v-else type="success" size="small" style="margin-top:4px">人</el-tag>
          </div>
        </div>
        <div v-if="!branches.length" style="text-align:center;color:#a0aec0;padding:20px">暂无分支数据</div>
      </el-card>
    </div>

    <!-- 近期检测 -->
    <div v-if="cachedResults.length" style="margin-top:24px">
      <h3 style="margin-bottom:12px;font-size:14px;color:#718096">近期检测</h3>
      <div v-for="r in cachedResults" :key="r.id" class="history-item" @click="loadHistory(r)">
        <span style="font-size:13px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ r.title }}</span>
        <span style="font-size:12px;color:#a0aec0">{{ r.timestamp }}</span>
        <el-tag :type="r.data?.is_ai_generated ? 'danger' : 'success'" size="small">
          {{ r.data?.is_ai_generated ? 'AI' : '人' }} {{ r.data?.confidence ? (r.data.confidence*100).toFixed(0)+'%' : '?' }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { Upload, Search, Microphone, VideoPause, CircleCheck, WarningFilled } from "@element-plus/icons-vue"
import { useResultsStore } from "@/stores/results"
import { usePollTask } from "@/composables/usePollTask"
import { extractApiErrorMessage } from "@/utils/errors"
import ConfidenceGauge from "@/components/detection/ConfidenceGauge.vue"
import { confidenceColor, riskTagType } from "@/utils/color"
import { formatSize } from "@/utils/format"

const file = ref<File | null>(null)
const audioUrl = ref("")
const detecting = ref(false)
const result = ref<any>(null)
const fileInput = ref<HTMLInputElement>()
const resultsStore = useResultsStore()
const { pollTask: pollTaskAsync } = usePollTask()
const cachedResults = computed(() => resultsStore.getLatest("audio").reverse())

const branches = computed(() => result.value?.explanation?.branches || [])

const verdictColor = computed(() => {
  if (!result.value) return "#718096"
  return result.value.is_ai_generated ? "#dc2626" : "#10b981"
})
const riskTagTypeComputed = computed(() => {
  if (!result.value?.risk_level) return "info"
  return riskTagType(result.value.risk_level)
})

watch(file, (f) => {
  if (f) {
    audioUrl.value = URL.createObjectURL(f)
  } else {
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value)
    audioUrl.value = ""
    result.value = null
  }
})

function branchLabel(name: string): string {
  const m: Record<string,string> = {
    wav2vec2_xlsr: "Wav2Vec2 XLS-R",
    resemble_api: "Resemble AI",
    rawnet2: "RawNet2",
  }
  return m[name] || name
}

// 使用公共颜色函数
const confColor = confidenceColor

function triggerUpload() { fileInput.value?.click() }

function handleFileInput(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files?.length) { file.value = t.files[0]; result.value = null }
}

function handleDrop(e: DragEvent) {
  if (e.dataTransfer?.files?.length) {
    file.value = e.dataTransfer.files[0]
    result.value = null
  }
}

async function handleDetect() {
  if (!file.value) { ElMessage.warning("请选择音频文件"); return }
  detecting.value = true; result.value = null
  try {
    const fd = new FormData()
    fd.append("file", file.value)
    fd.append("options", JSON.stringify({ explain: true }))
    const { data } = await api.post("/detect/audio", fd, {
      timeout: 60000,
    })
    if (data.status === "completed") {
      result.value = data
      resultsStore.add("audio", file.value.name.slice(0, 40), data)
    } else if (data.status === "processing") {
      ElMessage.info("检测任务已提交: " + data.task_id?.slice(0, 12))
      await pollTask(data.task_id)
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
      resultsStore.add("audio", file.value?.name?.slice(0, 40) || "音频", resultData)
    },
    (errMsg) => {
      ElMessage.error(errMsg)
    }
  )
}

function loadHistory(r: any) {
  result.value = r.data
  file.value = null
  audioUrl.value = ""
  window.scrollTo({ top: 0, behavior: "smooth" })
}
</script>

<style scoped>
.audio-detect { max-width: 700px; margin: 0 auto; }
.upload-zone {
  border: 2px dashed #d1d5db; border-radius: 12px; padding: 36px; text-align: center;
  background: #f9fafb; transition: all .3s; cursor: pointer;
}
.upload-zone:hover, .upload-zone.has-file { border-color: #409eff; background: #ecf5ff; }
.file-preview { text-align: left; }
.result-section { animation: fadeIn .5s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.verdict-card, .score-card { padding: 16px; text-align: center; }
.verdict-text { font-size: 22px; font-weight: 700; margin-top: 8px; }
.verdict-icon { margin-bottom: 4px; }
.branch-card { padding: 12px; background: #f8fafc; border-radius: 8px; text-align: center; }
.history-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; background: white; border-radius: 8px;
  border: 1px solid #e2e8f0; margin-bottom: 4px; cursor: pointer;
}
.history-item:hover { border-color: #409eff; }
</style>
