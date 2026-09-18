<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadRawFile } from 'element-plus'
import { submitPaper } from '@/api/detect'

const router = useRouter()

const DEGREES = [
  { key: 'BACHELOR', label: '本科', threshold: 20 },
  { key: 'MASTER',   label: '硕士', threshold: 15 },
  { key: 'PHD',      label: '博士', threshold: 10 },
] as const

const degree = ref<'BACHELOR' | 'MASTER' | 'PHD'>('BACHELOR')
const file = ref<UploadRawFile | null>(null)
const submitting = ref(false)

const threshold = computed(() => DEGREES.find(d => d.key === degree.value)?.threshold)

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

async function submit() {
  if (!file.value) return ElMessage.warning('请先选择论文文件')
  submitting.value = true
  try {
    const resp = await submitPaper(file.value, degree.value)
    ElMessage.success('提交成功，正在检测')
    router.push({ name: 'TaskDetail', params: { id: resp.taskId } })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="title">提交论文检测</span>
        <span></span>
      </div>
    </el-header>

    <el-main class="main">
      <el-card class="card">
        <el-form label-position="top">
          <el-form-item label="学位类型">
            <el-radio-group v-model="degree">
              <el-radio-button v-for="d in DEGREES" :key="d.key" :label="d.key">
                {{ d.label }}
              </el-radio-button>
            </el-radio-group>
            <div class="threshold-hint">教育部红线：AI 率 ≤ {{ threshold }}%</div>
          </el-form-item>

          <el-form-item label="论文文件（PDF / Word / TXT，≤ 20MB）">
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
                <div style="font-size: 48px">📎</div>
                <div>将文件拖到此处，或 <em>点击选择</em></div>
              </div>
            </el-upload>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary" size="large" :loading="submitting"
              :disabled="!file" @click="submit" style="width: 240px"
            >提交检测</el-button>
          </el-form-item>

          <div class="privacy">
            论文原文加密存储，30 天后自动删除；检测报告保留 3 年
          </div>
        </el-form>
      </el-card>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header { background: #fff; border-bottom: 1px solid #e5e7eb; padding: 0; }
.header-inner {
  height: 60px; padding: 0 24px; display: flex;
  justify-content: space-between; align-items: center;
}
.title { font-size: 16px; font-weight: 600; color: #111827; }
.main { padding: 32px 24px; display: flex; justify-content: center; }
.card { width: 100%; max-width: 720px; }
.threshold-hint { margin-top: 6px; font-size: 12px; color: #f59e0b; }
.upload-inner { padding: 24px 0; color: #6b7280; font-size: 14px; }
.upload-inner em { color: #1a56db; font-style: normal; }
.privacy { color: #9ca3af; font-size: 12px; text-align: center; margin-top: 12px; }
</style>
