<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { submitFeedback, type FeedbackCategory } from '@/api/feedback'
import { useAuthStore } from '@/stores/auth'

const props = defineProps<{
  modelValue: boolean
  /** 传入 taskId 时默认锁定为「结果申诉」入口，用于报告详情页 */
  taskId?: number
  /** 默认分类，profile 入口传 'suggestion'，详情页传 'appeal' */
  defaultCategory?: FeedbackCategory
  /** 报告段落（申诉时供勾选「哪几段判错了」） */
  paragraphs?: Array<{ paragraphIdx: number; text?: string; calibratedProb?: number | null; excluded?: boolean }>
}>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()

const auth = useAuthStore()

const category = ref<FeedbackCategory>(props.defaultCategory || (props.taskId ? 'appeal' : 'suggestion'))
const content = ref('')
const contact = ref('')
const submitting = ref(false)
const pickedIdxs = ref<number[]>([])
const consentImprove = ref(false)

/** 只列正文里「像 AI」的段（≥ 0.5），用户勾选判错的 */
const candidateParas = computed(() =>
  (props.paragraphs || [])
    .filter((p) => !p.excluded && (p.calibratedProb || 0) >= 0.5)
    .map((p) => ({ idx: p.paragraphIdx, prob: Math.round((p.calibratedProb || 0) * 100), preview: (p.text || '').slice(0, 40) })),
)

const remain = computed(() => 2000 - content.value.length)
const isAppeal = computed(() => category.value === 'appeal')
const canSubmit = computed(() => content.value.trim().length > 0 && content.value.length <= 2000)

// 弹窗每次打开时重置内容；appeal 场景保持锁定分类
watch(() => props.modelValue, (v) => {
  if (v) {
    category.value = props.defaultCategory || (props.taskId ? 'appeal' : 'suggestion')
    content.value = ''
    contact.value = ''
    pickedIdxs.value = []
    consentImprove.value = false
  }
})

function close() { emit('update:modelValue', false) }

async function onSubmit() {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    await submitFeedback({
      category: category.value,
      content: content.value.trim(),
      contact: contact.value.trim() || undefined,
      taskId: props.taskId,
      paragraphIdxs: isAppeal.value && pickedIdxs.value.length ? [...pickedIdxs.value].sort((a, b) => a - b) : undefined,
      consentImprove: isAppeal.value && pickedIdxs.value.length ? consentImprove.value : undefined,
      userId: auth.user?.id ? Number(auth.user.id) : undefined,
    })
    ElMessage.success('反馈已提交，我们会尽快查看')
    close()
  } catch (e: any) {
    // client 拦截器已弹 ElMessage.error
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue" width="480" align-center
    :title="taskId ? '结果申诉' : '意见反馈'"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="fb-body">
      <!-- appeal 入口锁定分类，其余场景可切换 bug/suggestion -->
      <el-radio-group v-if="!taskId" v-model="category" class="cat-group">
        <el-radio-button value="suggestion">功能建议</el-radio-button>
        <el-radio-button value="bug">问题反馈</el-radio-button>
      </el-radio-group>
      <div v-else class="appeal-hint">
        针对任务 #{{ taskId }} 的检测结果申诉，我们会人工复核并回复
      </div>

      <!-- 段级申诉：勾选判错的段，复核更快；同时是误判样本池的入口 -->
      <div v-if="isAppeal && candidateParas.length" class="para-pick">
        <div class="para-pick-title">哪几段判错了？（可多选，不选表示整体申诉）</div>
        <el-checkbox-group v-model="pickedIdxs" class="para-list">
          <el-checkbox v-for="p in candidateParas" :key="p.idx" :value="p.idx" class="para-item">
            <span class="para-tag">第 {{ p.idx + 1 }} 段 · {{ p.prob }}%</span>
            <span class="para-preview">{{ p.preview }}…</span>
          </el-checkbox>
        </el-checkbox-group>
        <el-checkbox v-model="consentImprove" :disabled="!pickedIdxs.length" class="consent">
          同意把勾选的段落用于改进检测模型（仅做内部评测，不公开、不用于训练；不勾只保留哈希）
        </el-checkbox>
      </div>

      <el-input
        v-model="content"
        type="textarea" :rows="6"
        :maxlength="2000" show-word-limit
        :placeholder="isAppeal
          ? '请描述你认为哪些段落被误判、依据是什么'
          : '请描述你遇到的问题或建议，越具体越好'"
      />

      <el-input
        v-model="contact"
        placeholder="联系方式（选填，方便我们回复）"
        maxlength="128"
        class="contact-input"
      />
    </div>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="onSubmit">
        提交
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.fb-body { display: flex; flex-direction: column; gap: 16px; }
.cat-group { align-self: flex-start; }
.appeal-hint {
  font-size: var(--fs-subhead, 14px);
  color: var(--label-secondary, rgba(60, 60, 67, 0.6));
  padding: 10px 14px;
  background: rgba(0, 122, 255, 0.08);
  border-radius: 10px;
}
.contact-input { max-width: 320px; }
.para-pick { background: #F2F2F7; border-radius: 10px; padding: 12px 14px; }
.para-pick-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.para-list { display: flex; flex-direction: column; gap: 4px; max-height: 180px; overflow-y: auto; }
.para-item :deep(.el-checkbox__label) { display: inline-flex; gap: 8px; align-items: baseline; }
.para-tag { font-size: 12px; color: #C62A22; font-weight: 600; white-space: nowrap; }
.para-preview { font-size: 12px; color: rgba(60,60,67,0.72); }
.consent { margin-top: 8px; font-size: 12px; }
.consent :deep(.el-checkbox__label) { font-size: 12px; white-space: normal; line-height: 1.4; }
</style>
