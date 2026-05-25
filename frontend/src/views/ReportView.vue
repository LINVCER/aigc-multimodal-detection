<template>
  <div>
    <h1>检测报告 #{{ taskId }}</h1>
    <el-card v-loading="loading" v-if="!loading && report">
      <el-alert
        :title="report.is_ai_generated ? 'AI 生成' : '人类写作'"
        :type="report.is_ai_generated ? 'error' : 'success'"
        :closable="false"
        show-icon
        style="margin-bottom:20px"
      />

      <el-descriptions :column="2" border style="margin-bottom:20px">
        <el-descriptions-item label="置信度">{{ (report.confidence * 100).toFixed(1) }}%</el-descriptions-item>
        <el-descriptions-item label="风险等级">
          <el-tag :type="riskType(report.confidence)" size="small">{{ riskText(report.confidence) }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="检测模态">{{ report.modality || 'text' }}</el-descriptions-item>
        <el-descriptions-item label="仲裁理由">{{ report.arbitration_reason || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="检测时间">{{ report.created_at || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="文本长度">{{ report.char_count || 'N/A' }} 字符</el-descriptions-item>
      </el-descriptions>

      <div v-if="report.explanation" style="margin-top:20px">
        <h3>详细分析</h3>
        <el-descriptions :column="1" border>
          <el-descriptions-item v-if="report.explanation.defense_warnings?.length" label="防御警告">
            <el-tag v-for="w in report.explanation.defense_warnings" :key="w" type="warning" size="small" style="margin:2px">{{ w }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="report.explanation.statistical_features" label="统计特征">
            <div v-for="(v, k) in report.explanation.statistical_features" :key="k" style="margin:2px 0">
              <strong>{{ k }}:</strong> {{ typeof v === 'number' ? v.toFixed(4) : v }}
            </div>
          </el-descriptions-item>
          <el-descriptions-item v-if="report.explanation.branch_outputs" label="模型分支">
            <div v-for="(v, k) in report.explanation.branch_outputs" :key="k" style="margin:2px 0">
              <el-tag size="small">{{ k }}</el-tag> 置信度: {{ typeof v === 'object' ? (v.confidence * 100).toFixed(1)+'%' : v }}
            </div>
          </el-descriptions-item>
          <el-descriptions-item v-if="report.explanation.suspicious_spans?.length" label="可疑片段">
            <el-tag
              v-for="(span, i) in report.explanation.suspicious_spans"
              :key="i"
              type="warning"
              size="small"
              style="margin:2px"
            >{{ span }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div v-if="report.content" style="margin-top:20px">
        <h3>检测文本</h3>
        <div class="content-preview">{{ report.content }}</div>
      </div>
    </el-card>

    <el-card v-else-if="loading">
      <el-skeleton :rows="10" animated />
    </el-card>

    <el-empty v-else description="报告未找到" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '@/api'

const route = useRoute()
const taskId = route.params.taskId as string
const report = ref<any>(null)
const loading = ref(true)

function riskType(c: number) { return c >= 0.8 ? 'danger' : c >= 0.5 ? 'warning' : 'success' }
function riskText(c: number) { return c >= 0.8 ? '高风险' : c >= 0.5 ? '中风险' : '低风险' }

onMounted(async () => {
  try {
    const { data } = await api.get(`/reports/${taskId}`)
    report.value = data.result || data
  } catch {
    report.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
h1 { margin-bottom: 20px; }
h3 { margin-bottom: 12px; font-size: 15px; }
.content-preview { white-space: pre-wrap; background: var(--el-fill-color-lighter); padding: 16px; border-radius: 6px; max-height: 400px; overflow-y: auto; font-size: 14px; line-height: 1.8; }
</style>
