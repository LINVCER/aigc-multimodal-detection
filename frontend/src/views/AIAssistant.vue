<template>
  <div class="ai-assistant">
    <h1>AI 助手</h1>
    <p style="color:#718096;margin-top:0">文档工具: 转 PDF、文字转语音</p>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 文档转 PDF -->
      <el-tab-pane label="文档转 PDF" name="pdf">
        <el-card>
          <div class="upload-zone" @click="triggerPdfUpload" @dragover.prevent @drop.prevent="handlePdfDrop">
            <div v-if="!pdfFile">
              <el-icon :size="48" color="#a0aec0"><Document /></el-icon>
              <p style="margin:12px 0 4px;font-size:15px;color:#4a5568">拖拽文档到此处或点击选择</p>
              <p style="font-size:13px;color:#a0aec0">支持 .txt / .docx</p>
            </div>
            <div v-else>
              <div style="font-weight:600;font-size:15px">{{ pdfFile.name }}</div>
              <div style="font-size:13px;color:#a0aec0">{{ formatSize(pdfFile.size) }}</div>
              <el-button size="small" type="danger" text @click.stop="pdfFile=null" style="margin-top:4px">移除</el-button>
            </div>
            <input ref="pdfInput" type="file" accept=".txt,.docx" style="display:none" @change="handlePdfFileInput" />
          </div>
          <el-button type="primary" size="large" @click="convertToPdf" :loading="converting" :disabled="!pdfFile"
            style="margin-top:16px;width:100%">
            <el-icon><MagicStick /></el-icon> {{ converting ? '转换中...' : '一键转换为 PDF' }}
          </el-button>
        </el-card>
        <el-alert v-if="pdfConverted" type="success" title="PDF 已生成并下载" show-icon style="margin-top:12px" closable @close="pdfConverted=false" />
      </el-tab-pane>

      <!-- 文字转语音 -->
      <el-tab-pane label="文字转语音" name="tts">
        <el-card>
          <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
            <div style="min-width:180px">
              <div style="font-size:13px;color:#718096;margin-bottom:4px">选择音色</div>
              <el-select v-model="selectedVoice" placeholder="选择音色" @change="previewVoice" style="width:100%">
                <el-option-group label="AI 合成">
                  <el-option v-for="v in aiVoices" :key="v.id" :label="v.name" :value="v.id">
                    <span>{{ v.name }}</span>
                    <el-tag size="small" type="warning" style="margin-left:8px">AI</el-tag>
                  </el-option>
                </el-option-group>
                <el-option-group label="微软 TTS">
                  <el-option v-for="v in edgeVoices" :key="v.id" :label="v.name" :value="v.id">
                    <span>{{ v.name }}</span>
                    <el-tag size="small" :type="v.gender==='女'?'danger':''" style="margin-left:8px">{{ v.gender }}</el-tag>
                  </el-option>
                </el-option-group>
              </el-select>
            </div>
            <div style="flex:1">
              <div style="font-size:13px;color:#718096;margin-bottom:4px">语速比例</div>
              <el-slider v-model="speechRate" :min="0.5" :max="2.0" :step="0.1" show-input size="small" />
            </div>
          </div>
          <el-input v-model="ttsText" type="textarea" :rows="6"
            placeholder="输入要转换为语音的文字... (5-3000字)" maxlength="3000" show-word-limit />
          <div style="margin-top:12px;display:flex;gap:8px">
            <el-button type="primary" @click="textToSpeech" :loading="synthesizing" :disabled="!ttsText.trim()">
              <el-icon><Microphone /></el-icon> 生成语音
            </el-button>
            <el-button v-if="audioUrl" @click="stopAudio" type="warning">
              <el-icon><Close /></el-icon> 停止
            </el-button>
            <el-button v-if="audioUrl" @click="downloadAudio" type="success">
              <el-icon><Download /></el-icon> 下载语音
            </el-button>
          </div>
          <div v-if="audioUrl" style="margin-top:16px">
            <audio :src="audioUrl" controls style="width:100%;height:40px" />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue"
import api from "@/api"
import { ElMessage } from "element-plus"
import { Document, MagicStick, Microphone, Close, Download } from "@element-plus/icons-vue"
import { formatSize } from "@/utils/format"

// Tabs
const activeTab = ref("pdf")

// === Document to PDF ===
const pdfFile = ref<File | null>(null)
const converting = ref(false)
const pdfConverted = ref(false)
const pdfInput = ref<HTMLInputElement>()

function triggerPdfUpload() { pdfInput.value?.click() }
function handlePdfFileInput(e: Event) {
  const t = e.target as HTMLInputElement
  if (t.files?.length) pdfFile.value = t.files[0]
}
function handlePdfDrop(e: DragEvent) {
  if (e.dataTransfer?.files?.length) pdfFile.value = e.dataTransfer.files[0]
}

async function convertToPdf() {
  if (!pdfFile.value) return
  converting.value = true
  try {
    const fd = new FormData(); fd.append("file", pdfFile.value)
    const { data } = await api.post("/assistant/convert-to-pdf", fd, {
      responseType: "blob",
    })
    const url = URL.createObjectURL(new Blob([data]))
    const a = document.createElement("a"); a.href = url
    a.download = pdfFile.value.name.replace(/\.[^.]+$/, ".pdf")
    a.click(); URL.revokeObjectURL(url)
    pdfConverted.value = true
    ElMessage.success("PDF 已下载")
  } catch { ElMessage.error("转换失败") }
  converting.value = false
}

// === Text to Speech ===
const ttsText = ref("")
const selectedVoice = ref("edge-xiaoxiao")
const speechRate = ref(1.0)
const synthesizing = ref(false)
const audioUrl = ref("")
const audioEl = ref<HTMLAudioElement | null>(null)

const voices = ref<any[]>([
  { id: "chattts", name: "ChatTTS (AI合成)", type: "ai" },
  { id: "edge-xiaoxiao", name: "晓晓 (女)", type: "edge", gender: "女" },
  { id: "edge-yunxi", name: "云希 (男)", type: "edge", gender: "男" },
  { id: "edge-xiaoyi", name: "晓依 (女)", type: "edge", gender: "女" },
  { id: "edge-yunjian", name: "云健 (男)", type: "edge", gender: "男" },
  { id: "edge-yunyang", name: "云扬 (男)", type: "edge", gender: "男" },
  { id: "edge-yunxia", name: "云夏 (男)", type: "edge", gender: "男" },
  { id: "edge-liaoning-xiaobei", name: "晓北(东北话)", type: "edge", gender: "女" },
  { id: "edge-HiuGaai", name: "晓佳(粤语)", type: "edge", gender: "女" },
])

const aiVoices = computed(() => voices.value.filter(v => v.type === "ai"))
const edgeVoices = computed(() => voices.value.filter(v => v.type === "edge"))

async function textToSpeech() {
  if (!ttsText.value.trim()) return
  synthesizing.value = true; audioUrl.value = ""
  try {
    const { data } = await api.post("/assistant/text-to-speech", {
      text: ttsText.value, voice: selectedVoice.value,
    }, { responseType: "blob" })
    audioUrl.value = URL.createObjectURL(new Blob([data]))
    ElMessage.success("语音生成完成")
  } catch { ElMessage.error("语音生成失败") }
  synthesizing.value = false
}

function stopAudio() {
  const audios = document.querySelectorAll("audio")
  audios.forEach(a => { a.pause(); a.currentTime = 0 })
}
function downloadAudio() {
  if (!audioUrl.value) return
  const a = document.createElement("a"); a.href = audioUrl.value
  a.download = `tts_${Date.now().toString(36)}.wav`; a.click()
}
function previewVoice(v: string) {
  selectedVoice.value = v
}
</script>

<style scoped>
.ai-assistant { max-width: 800px; margin: 0 auto; }
.upload-zone {
  border: 2px dashed #d1d5db; border-radius: 12px; padding: 36px; text-align: center;
  background: #f9fafb; transition: all .3s; cursor: pointer;
}
.upload-zone:hover { border-color: #409eff; background: #ecf5ff; }
</style>
