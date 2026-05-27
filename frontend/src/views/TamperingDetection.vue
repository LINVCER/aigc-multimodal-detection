<template>
  <div class="tampering-detect">
    <h1>篡改检测</h1>
    <p style="color:#718096;margin-top:0">
      检测图像是否存在拼接、复制粘贴等篡改痕迹 — 五路融合: Mask R-CNN + FFT频域 + 噪声不一致 + JPEG ELA + EXIF元数据
    </p>

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
        type="warning"
        size="large"
        @click="handleDetect"
        :loading="detecting"
        :disabled="!file"
        style="margin-top:12px;width:100%"
      >
        <template v-if="detecting">
          <el-icon class="is-loading"><Loading /></el-icon>
          篡改检测分析中... 约 5-10 秒
        </template>
        <template v-else>
          开始篡改检测
        </template>
      </el-button>
    </el-card>

    <!-- 检测结果 -->
    <el-card v-if="result" class="result-card" style="margin-top:20px">
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:600;font-size:16px">检测结果</span>
          <el-tag
            :type="result.is_tampered ? 'danger' : 'success'"
            size="large"
            effect="dark"
          >
            {{ result.is_tampered ? '检测到篡改' : '图像真实' }}
          </el-tag>
        </div>
      </template>

      <!-- 置信度仪表盘 -->
      <div class="gauge-section">
        <div class="gauge-ring" :style="{ '--pct': (result.tampering_score * 100).toFixed(0) }">
          <div class="gauge-inner">
            <span class="gauge-value">{{ (result.tampering_score * 100).toFixed(1) }}%</span>
            <span class="gauge-label">篡改置信度</span>
          </div>
        </div>

        <div class="risk-info">
          <div class="risk-item">
            <span class="risk-label">风险等级</span>
            <el-tag :type="riskTagTypeComputed" size="large">
              {{ riskTextComputed }}
            </el-tag>
          </div>
          <div class="risk-item">
            <span class="risk-label">篡改类型</span>
            <span class="risk-value">{{ tamperingTypeText(result.tampering_type) }}</span>
          </div>
        </div>
      </div>

      <!-- 提示信息 -->
      <div v-if="result.is_tampered && result.tampering_score > 0.7" style="margin-top:16px">
        <el-alert
          title="该图像极有可能经过篡改处理，请注意核实图像来源"
          type="error"
          show-icon
          :closable="false"
        />
      </div>
      <div v-else-if="!result.is_tampered && result.tampering_score < 0.2" style="margin-top:16px">
        <el-alert
          title="未检测到明显篡改痕迹，图像可能为原始未修改状态"
          type="success"
          show-icon
          :closable="false"
        />
      </div>
      <div v-else style="margin-top:16px">
        <el-alert
          title="检测结果存在不确定性，建议结合上下文人工判断"
          type="info"
          show-icon
          :closable="false"
        />
      </div>
    </el-card>

    <!-- 篡改区域可视化 -->
    <el-card v-if="result" style="margin-top:16px">
      <template #header>
        <span style="font-weight:600">篡改区域可视化</span>
      </template>
      <div v-if="result.overlay_image" class="visual-grid">
        <div class="visual-item">
          <span class="visual-label">原始图像</span>
          <img :src="previewUrl" alt="原始图像" />
        </div>
        <div class="visual-item">
          <span class="visual-label">篡改掩码</span>
          <img :src="result.mask_image" alt="篡改掩码" />
        </div>
        <div class="visual-item">
          <span class="visual-label">篡改标注</span>
          <img :src="result.overlay_image" alt="篡改标注" />
        </div>
      </div>
      <div v-else style="text-align:center;padding:24px;color:#a0aec0">
        <p>可视化图像未存储，请重新检测以查看篡改区域标注</p>
      </div>
      <div class="legend-bar">
        <span class="legend-item">
          <span class="legend-dot" style="background:rgba(255,0,0,0.4)"></span>确认篡改区域
        </span>
        <span class="legend-item">
          <span class="legend-dot" style="background:rgba(255,255,0,0.3)"></span>不确定区域
        </span>
        <span class="legend-item">
          <span class="legend-dot" style="background:#67c23a"></span>图像真实区域
        </span>
      </div>
    </el-card>

    <!-- 分支详情 -->
    <el-card v-if="result?.branches?.length" style="margin-top:16px">
      <template #header><span style="font-weight:600">五路检测分支详情</span></template>
      <div class="branch-grid">
        <div v-for="b in result.branches" :key="b.name" class="branch-card">
          <div class="branch-icon" :style="{ background: branchColor(b.name) }">
            {{ branchIcon(b.name) }}
          </div>
          <div class="branch-name">{{ branchDisplayName(b.name) }}</div>
          <el-progress
            :percentage="Math.round(b.confidence * 100)"
            :color="b.confidence > 0.6 ? '#ef4444' : b.confidence > 0.3 ? '#e6a23c' : '#10b981'"
            :stroke-width="8"
          />
          <div class="branch-verdict">
            <el-tag :type="b.is_tampered ? 'danger' : 'success'" size="small">
              {{ b.is_tampered ? '存在篡改' : '未检测到' }}
            </el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 检测历史 -->
    <div v-if="cachedResults.length > 0" style="margin-top:16px">
      <h3 style="margin-bottom:8px;font-size:14px;color:#718096">近期检测</h3>
      <div
        v-for="item in cachedResults"
        :key="item.id"
        class="history-item"
        @click="result = item.data; scrollToTop()"
      >
        <el-tag :type="item.data.is_tampered ? 'danger' : 'success'" size="small">
          {{ item.data.is_tampered ? '篡改' : '真实' }}
        </el-tag>
        <span class="history-title">{{ item.title }}</span>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:12px;color:#a0aec0">{{ item.timestamp }}</span>
          <span class="history-score">{{ (item.data.tampering_score * 100).toFixed(0) }}%</span>
          <el-button size="small" text type="danger" @click.stop="resultsStore.remove(item.id)">x</el-button>
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

const resultsStore = useResultsStore()
const { pollTask: pollTaskAsync } = usePollTask()

const fileInput = ref<HTMLInputElement>()
const file = ref<File | null>(null)
const previewUrl = ref("")
const detecting = ref(false)
const result = ref<any>(null)
const dragOver = ref(false)
const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' })

const cachedResults = computed(() => resultsStore.getLatest("tampering").reverse())

const riskTagTypeComputed = computed(() => riskTagType(result.value?.risk_level || "low"))
const riskTextComputed = computed(() => getRiskText(result.value?.risk_level || "low"))

const BRANCH_NAMES: Record<string, string> = {
  maskrcnn_resnet50_fpn: "Mask R-CNN 深度学习",
  fft_frequency_anomaly: "FFT 频域异常",
  noise_inconsistency: "噪声不一致",
  jpeg_ela: "JPEG ELA 压缩分析",
  exif_metadata: "EXIF 元数据一致性",
}

const BRANCH_COLORS: Record<string, string> = {
  maskrcnn_resnet50_fpn: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
  fft_frequency_anomaly: "linear-gradient(135deg, #f093fb 0%, #f5576c 100%)",
  noise_inconsistency: "linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)",
  jpeg_ela: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",
  exif_metadata: "linear-gradient(135deg, #fa709a 0%, #fee140 100%)",
}

const BRANCH_ICONS: Record<string, string> = {
  maskrcnn_resnet50_fpn: "D",
  fft_frequency_anomaly: "F",
  noise_inconsistency: "N",
  jpeg_ela: "E",
  exif_metadata: "X",
}

const TAMPERING_TYPES: Record<string, string> = {
  splicing: "拼接篡改",
  copy_move: "复制移动",
  inpainting: "修复擦除",
  retouching: "修饰美化",
  unknown: "未知类型",
}

function branchDisplayName(name: string): string {
  return BRANCH_NAMES[name] || name
}

function branchColor(name: string): string {
  return BRANCH_COLORS[name] || "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)"
}

function branchIcon(name: string): string {
  return BRANCH_ICONS[name] || "?"
}

function tamperingTypeText(type: string): string {
  return TAMPERING_TYPES[type] || type || "未知"
}

function triggerUpload() {
  fileInput.value?.click()
}

function handleDrop(e: DragEvent) {
  dragOver.value = false
  const files = e.dataTransfer?.files
  if (files?.length) setFile(files[0])
}

function handleFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.length) setFile(target.files[0])
}

function setFile(f: File) {
  const valid = f.type.startsWith("image/") || /\.(jpg|jpeg|png|webp|bmp|gif|tiff?)$/i.test(f.name)
  if (!valid) {
    ElMessage.warning("请选择图像文件")
    return
  }
  file.value = f
  previewUrl.value = URL.createObjectURL(f)
  result.value = null
}

function reset() {
  file.value = null
  previewUrl.value = ""
  result.value = null
  if (fileInput.value) fileInput.value.value = ""
}

async function handleDetect() {
  if (!file.value) {
    ElMessage.warning("请选择图像文件")
    return
  }
  detecting.value = true
  result.value = null
  const startTime = Date.now()

  try {
    const formData = new FormData()
    formData.append("file", file.value)

    // 显示进度提示
    const loadingMsg = ElMessage({
      message: "篡改检测分析中，请稍候...",
      type: "info",
      duration: 0,
    })

    const { data } = await api.post("/detect/tampering", formData, {
      timeout: 180000, // 增加超时时间到3分钟
    })

    loadingMsg.close()

    if (data.status === "completed") {
      result.value = data
      resultsStore.add("tampering", file.value.name, data)
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
      ElMessage.success(`检测完成，耗时 ${elapsed} 秒`)
    } else if (data.task_id) {
      ElMessage.success("检测任务已提交: " + data.task_id)
      await pollTask(data.task_id)
    } else {
      // 处理未知响应格式
      result.value = data
      resultsStore.add("tampering", file.value.name, data)
    }
  } catch (e: any) {
    const errMsg = extractApiErrorMessage(e, "篡改检测失败")
    if (errMsg.includes("timeout") || errMsg.includes("超时")) {
      ElMessage.error("检测超时，请尝试上传较小的图片或稍后重试")
    } else {
      ElMessage.error(errMsg)
    }
  } finally {
    detecting.value = false
  }
}

async function pollTask(taskId: string) {
  await pollTaskAsync(
    taskId,
    (resultData) => {
      result.value = resultData
      resultsStore.add("tampering", file.value?.name || "篡改检测", resultData)
    },
    (errMsg) => {
      ElMessage.error(errMsg)
    },
  )
}
</script>

<style scoped>
.tampering-detect {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

/* 上传区域 */
.upload-zone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #f9fafb;
}

.upload-zone:hover,
.upload-zone.is-dragover {
  border-color: #e6a23c;
  background: #fdf6ec;
}

.upload-zone.has-image {
  padding: 12px;
}

.preview-img {
  max-width: 100%;
  max-height: 360px;
  border-radius: 8px;
  display: block;
  margin: 0 auto;
}

/* 结果卡片 */
.result-card {
  border-left: 4px solid #e6a23c;
  animation: fadeIn 0.4s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 仪表盘 */
.gauge-section {
  display: flex;
  align-items: center;
  gap: 32px;
  padding: 16px 0;
}

.gauge-ring {
  --pct: 50;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: conic-gradient(
    #ef4444 calc(var(--pct) * 1%),
    #10b981 calc(var(--pct) * 1%)
  );
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
}

.gauge-ring::before {
  content: "";
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

.gauge-value {
  font-size: 28px;
  font-weight: 700;
  color: #1a202c;
  display: block;
}

.gauge-label {
  font-size: 12px;
  color: #718096;
  margin-top: 2px;
}

.risk-info {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.risk-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.risk-label {
  font-size: 13px;
  color: #718096;
}

.risk-value {
  font-size: 18px;
  font-weight: 600;
  color: #1a202c;
}

/* 可视化网格 */
.visual-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.visual-item {
  text-align: center;
}

.visual-item img {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f7fafc;
}

.visual-label {
  display: block;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 8px;
  color: #4a5568;
}

.legend-bar {
  margin-top: 16px;
  display: flex;
  gap: 24px;
  justify-content: center;
  font-size: 12px;
  color: #718096;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

/* 分支卡片 */
.branch-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.branch-card {
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f9fafb;
  text-align: center;
  transition: box-shadow 0.2s;
}

.branch-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.branch-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 8px;
  font-size: 16px;
  font-weight: 800;
  color: white;
}

.branch-name {
  font-weight: 600;
  font-size: 13px;
  color: #1a202c;
  margin-bottom: 8px;
}

.branch-verdict {
  margin-top: 8px;
}

/* 历史记录 */
.history-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  border-color: #e6a23c;
  background: #fdf6ec;
}

.history-title {
  flex: 1;
  font-size: 13px;
  color: #4a5568;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-score {
  font-size: 12px;
  font-weight: 600;
  color: #e6a23c;
}

/* 响应式 */
@media (max-width: 768px) {
  .tampering-detect {
    padding: 12px;
  }

  .visual-grid {
    grid-template-columns: 1fr;
  }

  .gauge-section {
    flex-direction: column;
    align-items: flex-start;
  }

  .branch-grid {
    grid-template-columns: 1fr 1fr;
  }

  .legend-bar {
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }
}

@media (max-width: 480px) {
  .branch-grid {
    grid-template-columns: 1fr;
  }
}
</style>
