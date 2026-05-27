<template>
  <div>
    <h1>检测历史</h1>
    <el-card>
      <el-table :data="items" v-loading="loading" empty-text="暂无检测记录">
        <el-table-column prop="task_id" label="任务ID" width="100" />
        <el-table-column label="检测内容" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <span style="color:#718096;font-size:13px">{{ row.input_content || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="modality" label="模态" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ ({ text: '文本', image: '图像', audio: '音频', tampering: '篡改' } as Record<string,string>)[row.modality] || row.modality }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <template v-if="row.status === 'completed'">
              <el-tag v-if="row.modality === 'tampering'" :type="row.is_ai_generated ? 'danger' : 'success'" size="small">
                {{ row.is_ai_generated ? '篡改' : '真实' }}
              </el-tag>
              <el-tag v-else :type="row.is_ai_generated ? 'danger' : 'success'" size="small">
                {{ row.is_ai_generated ? 'AI' : '真人' }}
              </el-tag>
            </template>
            <el-tag v-else type="info" size="small">{{ row.status === 'failed' ? '失败' : '处理中' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="置信度" width="90">
          <template #default="{ row }">
            {{ row.confidence ? (row.confidence * 100).toFixed(0) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/report/${row.task_id}`)" v-if="row.status === 'completed'">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="prev, pager, next"
        style="margin-top:16px;justify-content:center"
        @current-change="fetchHistory"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue"
import api from "@/api"

const items = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(20)
const total = ref(0)

async function fetchHistory() {
  loading.value = true
  try {
    const { data } = await api.get("/reports/history/list", { params: { page: page.value, size: size.value } })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(() => fetchHistory())
</script>
