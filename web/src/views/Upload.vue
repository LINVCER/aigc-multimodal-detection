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

function humanBytes(n?: number) {
  if (!n) return ''
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

async function submit() {
  if (!file.value) return ElMessage.warning('请先选择论文文件')
  submitting.value = true
  try {
    const resp = await submitPaper(file.value, degree.value)
    ElMessage.success('提交成功，正在检测')
    router.push({ name: 'TaskDetail', params: { id: resp.taskId } })
  } finally { submitting.value = false }
}
</script>

<template>
  <el-container class="page">
    <el-header class="header">
      <div class="header-inner">
        <el-button link @click="router.back()">← 返回</el-button>
        <span class="header-title">上传检测</span>
        <span></span>
      </div>
    </el-header>

    <el-main class="main">
      <div class="wrap">
        <h1 class="large-title">上传检测</h1>

        <!-- Group 1: 学位类型 -->
        <div class="group-label">学位类型</div>
        <el-card class="group-card">
          <el-radio-group v-model="degree">
            <el-radio-button v-for="d in DEGREES" :key="d.key" :value="d.key">
              {{ d.label }}
            </el-radio-button>
          </el-radio-group>
          <div class="footnote">
            教育部红线：AI 率 <span class="footnote-strong">≤ {{ threshold }}%</span>
          </div>
        </el-card>

        <!-- Group 2: 文件 -->
        <div class="group-label">论文文件</div>
        <el-card class="group-card">
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
              <div class="upload-icon">􀈕</div>
              <div class="upload-text">
                <div class="upload-title">拖入文件 或 <em>点击选择</em></div>
                <div class="upload-sub">PDF / Word / TXT · 最大 20MB</div>
              </div>
            </div>
          </el-upload>
          <div v-if="file" class="file-picked">
            <span class="file-name">{{ file.name }}</span>
            <span class="file-size">{{ humanBytes(file.size) }}</span>
          </div>
        </el-card>

        <!-- Submit -->
        <el-button
          type="primary" round size="large"
          :loading="submitting" :disabled="!file"
          style="width: 100%; margin-top: 24px; height: 50px; font-size: 17px"
          @click="submit"
        >提交检测</el-button>

        <div class="privacy">
          论文原文加密存储，30 天后自动删除；检测报告保留 3 年
        </div>
      </div>
    </el-main>
  </el-container>
</template>

<style scoped>
.page { min-height: 100vh; }
.header {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  border-bottom: 1px solid var(--label-quaternary);
  padding: 0; position: sticky; top: 0; z-index: 10;
}
.header-inner { height: 56px; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; }
.header-title { font-size: var(--fs-headline); font-weight: var(--fw-semibold); }

.main { padding: 32px 24px 48px; }
.wrap { max-width: 640px; margin: 0 auto; }

.large-title {
  font-size: var(--fs-large-title);
  font-weight: var(--fw-bold);
  letter-spacing: -0.8px;
  margin: 0 0 24px;
}

.group-label {
  font-size: var(--fs-caption-1);
  font-weight: var(--fw-medium);
  color: var(--label-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 16px 12px 8px;
}
.group-card { margin-bottom: 8px; }

.footnote { margin-top: 12px; font-size: var(--fs-footnote); color: var(--label-secondary); }
.footnote-strong { color: var(--system-orange); font-weight: var(--fw-semibold); }

.upload-inner {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 0;
}
.upload-icon {
  width: 48px; height: 48px; border-radius: 10px;
  background: rgba(0, 122, 255, 0.10);
  color: var(--system-blue);
  font-size: 22px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.upload-text { text-align: left; }
.upload-title { font-size: var(--fs-body); font-weight: var(--fw-medium); color: var(--label); }
.upload-title em { color: var(--system-blue); font-style: normal; font-weight: var(--fw-semibold); }
.upload-sub { font-size: var(--fs-caption-1); color: var(--label-secondary); margin-top: 4px; }

.file-picked {
  margin-top: 12px;
  padding: 10px 14px;
  background: rgba(0, 122, 255, 0.06);
  border-radius: 8px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: var(--fs-subhead);
}
.file-name { color: var(--label); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { color: var(--label-secondary); flex-shrink: 0; margin-left: 12px; }

.privacy {
  margin-top: 24px;
  font-size: var(--fs-caption-1);
  color: var(--label-secondary);
  text-align: center;
}
</style>
