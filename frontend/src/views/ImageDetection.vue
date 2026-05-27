<template>
  <div class="image-detect">
    <h1>图像检测</h1>
    <p style="color:#718096;margin-top:0">检测图像是否由 AI 模型生成 — 三路融合: 高频噪声CNN + CLIP-ViT + MiMo-VL</p>

    <!-- 上传区域 -->
    <el-card>
      <div
        class="upload-zone"
        :class="{ 'has-image': previewUrl, 'is-dragover': dragOver }"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop"
        @click="triggerUpload"
      >
        <div v-if="!previewUrl">
          <el-icon :size="48" color="#a0aec0"><UploadFilled /></el-icon>
          <p style="margin:12px 0 4px;color:#4a5568">拖拽图片到此处，或点击选择</p>
          <p style="font-size:12px;color:#a0aec0">支持 JPG / PNG / WebP / BMP</p>
        </div>
        <img v-else :src="previewUrl" class="preview-img" />
      </div>
      <input
        ref="fileInput"
        type="file"
        accept="image/*"
        style="display:none"
        @change="handleFileInput"
      />

      <div v-if="file" style="margin-top:12px;display:flex;align-items:center;gap:12px">
        <el-tag type="info">{{ file.name }}</el-tag>
        <span style="color:#718096;font-size:13px">{{ (file.size / 1024).toFixed(1) }} KB</span>
        <el-button size="small" @click="reset">清除</el-button>
      </div>

      <el-button
        type="success"
        size="large"
        @click="handleDetect"
        :loading="detecting"
        :disabled="!file"
        style="margin-top:12px;width:100%"
      >
        <template v-if="detecting">
          <el-icon class="is-loading"><Loading /></el-icon>
          AI 模型分析中... 约 30 秒
        </template>
        <template v-else>
          开始检测
        </template>
      </el-button>
    </el-card>

    <!-- 检测结果 -->
    <el-card v-if="result" class="result-card" style="margin-top:20px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600;font-size:16px">检测结果</span>
          <el-tag
            :type="result.is_ai_generated ? 'danger' : 'success'"
            size="large"
            effect="dark"
          >
            {{ result.is_ai_generated ? 'AI 生成' : '真实图像' }}
          </el-tag>
        </div>
      </template>

      <!-- 置信度仪表盘 -->
      <div class="gauge-section">
        <div class="gauge-ring" :style="{ '--pct': (result.confidence * 100).toFixed(0) }">
          <div class="gauge-inner">
            <span class="gauge-value">{{ (result.confidence * 100).toFixed(1) }}%</span>
            <span class="gauge-label">AI 生成概率</span>
          </div>
        </div>

        <div class="risk-info">
          <div class="risk-item">
            <span class="risk-label">风险等级</span>
            <el-tag
              :type="riskTagTypeComputed"
              size="large"
            >
              {{ riskTextComputed }}
            </el-tag>
          </div>
          <div class="risk-item">
            <span class="risk-label">校准置信度</span>
            <span class="risk-value">{{ result.calibrated_confidence != null ? (result.calibrated_confidence * 100).toFixed(1) + '%' : 'N/A' }}</span>
          </div>
        </div>
      </div>

      <!-- 提示信息 -->
      <div v-if="result.is_ai_generated && result.confidence > 0.8" style="margin-top:16px">
        <el-alert
          title="该图像极可能由 AI 生成，建议人工复核"
          type="warning"
          show-icon
          :closable="false"
        />
      </div>
      <div v-else-if="!result.is_ai_generated && result.confidence < 0.3" style="margin-top:16px">
        <el-alert
          title="该图像大概率是真实拍摄的"
          type="success"
          show-icon
          :closable="false"
        />
      </div>
      <div v-else style="margin-top:16px">
        <el-alert
          title="检测结果不确定，建议人工判断"
          type="info"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>

    <!-- 分支详情 -->
    <el-card v-if="result && branches.length" style="margin-top:16px">
      <template #header><span style="font-weight:600">检测分支详情</span></template>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px">
        <div v-for="b in branches" :key="b.name" class="branch-card">
          <div style="font-weight:600;font-size:14px;margin-bottom:6px">{{ b.name }}</div>
          <el-progress
            :percentage="Math.round(b.confidence * 100)"
            :color="b.confidence > 0.5 ? '#ef4444' : '#10b981'"
            :stroke-width="8"
          />
          <div style="font-size:12px;color:#a0aec0;margin-top:4px">
            判定: {{ b.is_ai ? 'AI生成' : '真实' }}
          </div>
        </div>
      </div>
    </el-card>

    <!-- MiMo-VL 分析 -->
    <el-card v-if="result?.explanation?.mimo_explanation?.note" style="margin-top:12px">
      <template #header><span style="font-weight:600">MiMo-VL 视觉分析</span></template>
      <p style="font-size:13px;color:#4a5568;margin:0">{{ result.explanation.mimo_explanation.note }}</p>
    </el-card>

    <div v-if="cachedResults.length > 0" style="margin-top:16px">
      <h3 style="margin-bottom:8px;font-size:14px;color:#718096">近期检测</h3>
      <div v-for="r in cachedResults" :key="r.id"
        style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;background:white;border-radius:6px;border:1px solid #e2e8f0;margin-bottom:4px;cursor:pointer"
        @click="result=r.data;scrollToTop()">
        <span style="font-size:13px">{{ r.title }}</span>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:12px;color:#a0aec0">{{ r.timestamp }}</span>
          <el-tag :type="r.data?.is_ai_generated?'danger':'success'" size="small">
            {{ r.data?.is_ai_generated?'AI':'REAL' }} {{ (r.data?.confidence*100).toFixed(0) }}%
          </el-tag>
          <el-button size="small" text type="danger" @click.stop="resultsStore.remove(r.id)">x</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { UploadFilled, Loading } from "@element-plus/icons-vue"
import { useResultsStore } from "@/stores/results"
import { usePollTask } from "@/composables/usePollTask"
import { extractApiErrorMessage } from "@/utils/errors"
import { riskTagType, riskText as getRiskText } from "@/utils/color"

const file = ref<File | null>(null)
const previewUrl = ref<string>("")
const detecting = ref(false)
const result = ref<any>(null)
const resultsStore = useResultsStore()
const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })
const { pollTask: pollTaskAsync } = usePollTask()
const cachedResults = computed(() => resultsStore.getLatest("image").reverse())
const dragOver = ref(false)
const fileInput = ref<HTMLInputElement>()

const branches = computed(() => result.value?.explanation?.branches || [])

const riskTagTypeComputed = computed(() => {
  const r = result.value?.risk_level
  return riskTagType(r || 'low')
})

const riskTextComputed = computed(() => {
  const r = result.value?.risk_level
  return getRiskText(r || 'low')
})

function triggerUpload() {
  fileInput.value?.click()
}

function reset() {
  file.value = null
  previewUrl.value = ""
  result.value = null
  if (fileInput.value) fileInput.value.value = ""
}

function handleFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.length) {
    setFile(target.files[0])
  }
}

function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) {
    setFile(files[0])
  }
}

function setFile(f: File) {
  if (!f.type.startsWith("image/")) {
    ElMessage.warning("请选择图像文件")
    return
  }
  file.value = f
  previewUrl.value = URL.createObjectURL(f)
  result.value = null
}

async function handleDetect() {
  if (!file.value) { ElMessage.warning("请选择图像文件"); return }
  detecting.value = true
  result.value = null
  try {
    const formData = new FormData()
    formData.append("file", file.value)
    const { data } = await api.post("/detect/image", formData, {
      timeout: 120000,
    })
    if (data.status === "completed") {
      result.value = data
      resultsStore.add("image", file.value?.name || "图像", data)
    } else if (data.status === "processing") {
      ElMessage.success("检测任务已提交: " + data.task_id)
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
      resultsStore.add("image", file.value?.name || "图像", resultData)
    },
    (errMsg) => {
      ElMessage.error(errMsg)
    }
  )
}
</script>

<style scoped>
.image-detect { max-width: 680px; margin: 0 auto; }
.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #f9fafb;
}
.upload-zone:hover { border-color: #409eff; background: #ecf5ff; }
.upload-zone.has-image { padding: 12px; }
.upload-zone.is-dragover { border-color: #409eff; background: #ecf5ff; }
.preview-img { max-width: 100%; max-height: 360px; border-radius: 8px; display: block; margin: 0 auto; }

.gauge-section {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 16px 0;
}

.gauge-ring {
  --pct: 50;
  width: 140px; height: 140px;
  border-radius: 50%;
  background: conic-gradient(
    #ef4444 calc(var(--pct) * 1%),
    #10b981 calc(var(--pct) * 1%)
  );
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.gauge-ring::before {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  background: white;
}
.gauge-inner {
  position: relative;
  z-index: 1;
  text-align: center;
}
.gauge-value { font-size: 28px; font-weight: 700; color: #1a202c; display: block; }
.gauge-label { font-size: 12px; color: #718096; margin-top: 2px; }

.risk-info { display: flex; flex-direction: column; gap: 16px; }
.risk-item { display: flex; flex-direction: column; gap: 4px; }
.risk-label { font-size: 13px; color: #718096; }
.risk-value { font-size: 18px; font-weight: 600; color: #1a202c; }

.branch-card {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f9fafb;
  text-align: center;
}

.result-card { animation: fadeIn 0.4s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
</style>
