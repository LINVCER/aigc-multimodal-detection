<template>
  <el-card class="preprocessor" shadow="hover">
    <template #header>
      <div class="preprocessor-header">
        <span><el-icon><Brush /></el-icon> 文本预处理</span>
        <el-switch v-model="enabled" active-text="启用" />
      </div>
    </template>

    <div v-if="enabled" class="preprocessor-body">
      <div class="clean-options">
        <el-checkbox v-model="cleanHtml">去 HTML 标签</el-checkbox>
        <el-checkbox v-model="cleanRefs">去引用标记 [1][2]</el-checkbox>
        <el-checkbox v-model="cleanSpaces">去多余空格空行</el-checkbox>
        <el-checkbox v-model="normalizePunct">标点标准化（全角→半角）</el-checkbox>
      </div>

      <div class="stats-row">
        <el-tag size="small">字符: {{ charCount }}</el-tag>
        <el-tag size="small" type="info">段落: {{ paraCount }}</el-tag>
        <el-tag size="small" type="warning" v-if="langHint">{{ langHint }}</el-tag>
      </div>

      <el-button type="primary" size="small" @click="applyClean" :loading="cleaning" style="margin-top:12px">
        应用预处理
      </el-button>

      <el-collapse v-if="showDiff" style="margin-top:12px">
        <el-collapse-item title="查看预处理前后对比" name="diff">
          <div class="diff-container">
            <div class="diff-pane">
              <div class="diff-label">原始 ({{ originalCharCount }} 字符)</div>
              <div class="diff-text">{{ originalText }}</div>
            </div>
            <div class="diff-pane">
              <div class="diff-label">处理后 ({{ cleanedCharCount }} 字符)</div>
              <div class="diff-text">{{ cleanedText }}</div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Brush } from '@element-plus/icons-vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits(['update:modelValue', 'cleaned'])

const enabled = ref(true)
const cleanHtml = ref(true)
const cleanRefs = ref(true)
const cleanSpaces = ref(true)
const normalizePunct = ref(true)
const cleaning = ref(false)
const showDiff = ref(false)

const originalText = ref('')
const cleanedText = ref('')
const originalCharCount = ref(0)
const cleanedCharCount = ref(0)

const charCount = computed(() => props.modelValue.length)
const paraCount = computed(() => {
  if (!props.modelValue) return 0
  return props.modelValue.split(/\n\s*\n/).filter((p: string) => p.trim()).length
})
const langHint = computed(() => {
  const t = props.modelValue
  if (!t) return ''
  const cn = (t.match(/[一-鿿]/g) || []).length
  const en = (t.match(/[a-zA-Z]/g) || []).length
  if (cn > en * 2) return '中文为主'
  if (en > cn * 2) return '英文为主'
  return cn > 0 ? '中英混合' : ''
})

function applyClean() {
  cleaning.value = true
  let text = props.modelValue
  originalText.value = text
  originalCharCount.value = text.length

  if (cleanHtml.value) {
    text = text.replace(/<[^>]*>/g, '')
    text = text.replace(/&[a-z]+;/gi, '')
  }
  if (cleanRefs.value) {
    text = text.replace(/\[\d+(?:[,，\s]*\d+)*\]/g, '')
    text = text.replace(/\[\d+[-–—]\d+\]/g, '')
  }
  if (cleanSpaces.value) {
    text = text.replace(/[^\S\n]{3,}/g, ' ')
    text = text.replace(/\n{3,}/g, '\n\n')
    text = text.replace(/^[ \t]+/gm, '')
  }
  if (normalizePunct.value) {
    text = text.replace(/[，。《》「」『』【】；：？！、—]/g, (m: string) => {
      const map: Record<string, string> = {
        '，': ',', '。': '.', '《': '<', '》': '>', '「': '"', '」': '"',
        '『': "'", '』': "'", '【': '[', '】': ']', '；': ';', '：': ':',
        '？': '?', '！': '!', '、': ',', '—': '-'
      }
      return map[m] || m
    })
  }

  text = text.trim()
  cleanedText.value = text
  cleanedCharCount.value = text.length
  showDiff.value = text !== originalText.value

  emit('update:modelValue', text)
  emit('cleaned', {
    original: originalText.value,
    cleaned: text,
    changes: {
      charsRemoved: originalCharCount.value - cleanedCharCount.value,
      htmlStripped: cleanHtml.value,
      refsStripped: cleanRefs.value,
    }
  })
  cleaning.value = false
}

watch(() => props.modelValue, () => { showDiff.value = false })
</script>

<style scoped>
.preprocessor { margin-bottom: 16px; }
.preprocessor-header { display: flex; justify-content: space-between; align-items: center; }
.clean-options { display: flex; flex-wrap: wrap; gap: 12px; }
.stats-row { display: flex; gap: 8px; margin-top: 12px; }
.diff-container { display: flex; gap: 12px; }
.diff-pane { flex: 1; max-height: 300px; overflow-y: auto; }
.diff-label { font-weight: 600; margin-bottom: 4px; font-size: 13px; color: var(--el-color-info); }
.diff-text { white-space: pre-wrap; font-size: 13px; line-height: 1.6; padding: 8px; background: var(--el-fill-color-light); border-radius: 4px; }
</style>
