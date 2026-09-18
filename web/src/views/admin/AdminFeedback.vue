<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { listFeedbackAdmin, handleFeedback, type FeedbackItem, type FeedbackStatus } from '@/api/feedback'

const router = useRouter()

const filter = reactive<{ status: FeedbackStatus | ''; keyword: string }>({ status: '', keyword: '' })
const total = ref(0)
const pageNum = ref(1)
const pageSize = ref(20)
const rows = ref<FeedbackItem[]>([])
const loading = ref(false)

const CATEGORY_LABEL: Record<string, string> = { bug: '🐞 Bug', suggestion: '💡 建议', appeal: '🚩 结果申诉' }
const STATUS_TAG: Record<FeedbackStatus, { text: string; type: 'success' | 'danger' | 'warning' | 'info' }> = {
  PENDING:    { text: '待处理', type: 'warning' },
  PROCESSING: { text: '处理中', type: 'info'    },
  REPLIED:    { text: '已回复', type: 'success' },
  IGNORED:    { text: '已忽略', type: 'info'    },
}

async function load() {
  loading.value = true
  try {
    const resp = await listFeedbackAdmin({ ...filter, pageNum: pageNum.value, pageSize: pageSize.value })
    rows.value = resp.rows
    total.value = resp.total
  } finally { loading.value = false }
}
function search() { pageNum.value = 1; load() }
function reset() { Object.assign(filter, { status: '', keyword: '' }); search() }

/* ==================== 处理弹窗 ==================== */

const replyOpen = ref(false)
const current = ref<FeedbackItem | null>(null)
const replyStatus = ref<FeedbackStatus>('REPLIED')
const replyText = ref('')
const submitting = ref(false)

function openReply(row: FeedbackItem) {
  current.value = row
  replyStatus.value = row.status === 'REPLIED' ? 'REPLIED' : 'REPLIED'
  replyText.value = row.handledReply || ''
  replyOpen.value = true
}

async function submitReply() {
  if (!current.value) return
  if (replyStatus.value === 'REPLIED' && !replyText.value.trim()) {
    ElMessage.warning('回复内容不能为空')
    return
  }
  submitting.value = true
  try {
    await handleFeedback(current.value.id, {
      status: replyStatus.value,
      reply: replyText.value.trim() || undefined,
    })
    ElMessage.success('已保存')
    replyOpen.value = false
    load()
  } finally { submitting.value = false }
}

function viewAppealTask(id: number) { router.push(`/task/${id}`) }

onMounted(load)
</script>

<template>
  <el-card class="filter-card">
    <div class="filter-row">
      <el-select v-model="filter.status" placeholder="状态" clearable style="width: 130px">
        <el-option label="待处理" value="PENDING" />
        <el-option label="处理中" value="PROCESSING" />
        <el-option label="已回复" value="REPLIED" />
        <el-option label="已忽略" value="IGNORED" />
      </el-select>
      <el-input v-model="filter.keyword" placeholder="内容 / 联系方式" clearable style="width: 260px" @keyup.enter="search" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="reset">重置</el-button>
    </div>
  </el-card>

  <el-card class="table-card">
    <el-table v-loading="loading" :data="rows" size="default" empty-text="暂无反馈">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="分类" width="120">
        <template #default="{ row }">{{ CATEGORY_LABEL[row.category] || row.category }}</template>
      </el-table-column>
      <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip />
      <el-table-column label="关联任务" width="120">
        <template #default="{ row }">
          <el-button v-if="row.taskId" size="small" link type="primary" @click="viewAppealTask(row.taskId)">
            #{{ row.taskId }}
          </el-button>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="contact" label="联系方式" width="160">
        <template #default="{ row }">{{ row.contact || '—' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="STATUS_TAG[row.status as FeedbackStatus]?.type" size="small">
            {{ STATUS_TAG[row.status as FeedbackStatus]?.text || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="提交时间" width="170" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="openReply(row)">
            {{ row.status === 'REPLIED' || row.status === 'IGNORED' ? '查看' : '处理' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      v-model:current-page="pageNum"
      v-model:page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50, 100]"
      layout="total, sizes, prev, pager, next"
      @size-change="load"
      @current-change="load"
    />
  </el-card>

  <el-dialog v-model="replyOpen" width="520" title="处理反馈" align-center>
    <div v-if="current" class="reply-body">
      <div class="orig">
        <div class="orig-meta">
          <span>{{ CATEGORY_LABEL[current.category] }}</span>
          <span class="muted"> · #{{ current.id }} · {{ current.createdAt }}</span>
        </div>
        <div class="orig-content">{{ current.content }}</div>
        <div v-if="current.contact" class="orig-contact">联系方式：{{ current.contact }}</div>
        <div v-if="current.taskId" class="orig-task">
          关联任务：
          <el-button size="small" link type="primary" @click="viewAppealTask(current.taskId)">#{{ current.taskId }}</el-button>
        </div>
      </div>
      <el-radio-group v-model="replyStatus">
        <el-radio value="REPLIED">已回复</el-radio>
        <el-radio value="PROCESSING">处理中</el-radio>
        <el-radio value="IGNORED">已忽略</el-radio>
      </el-radio-group>
      <el-input
        v-model="replyText" type="textarea" :rows="5"
        placeholder="回复内容（REPLIED 状态必填）"
      />
    </div>
    <template #footer>
      <el-button @click="replyOpen = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submitReply">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.filter-card { margin-bottom: 16px; }
.filter-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.table-card :deep(.el-card__body) { padding: 0; }
.pager { justify-content: flex-end; padding: 16px; }
.muted { color: rgba(60,60,67,0.60); }

.reply-body { display: flex; flex-direction: column; gap: 14px; }
.orig {
  background: #F2F2F7;
  border-radius: 10px;
  padding: 14px;
  font-size: 13px;
}
.orig-meta { font-weight: 600; margin-bottom: 6px; }
.orig-content { color: #1C1C1E; white-space: pre-wrap; }
.orig-contact, .orig-task { margin-top: 8px; color: rgba(60,60,67,0.72); }
</style>
