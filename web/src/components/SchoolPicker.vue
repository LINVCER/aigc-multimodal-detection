<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { searchSchools, setMySchool, type School } from '@/api/school'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void; (e: 'saved'): void }>()

const q = ref('')
const list = ref<School[]>([])
const loading = ref(false)
const picked = ref<School | null>(null)
const degree = ref('master')

let timer: ReturnType<typeof setTimeout> | undefined
function onInput() {
  clearTimeout(timer)
  timer = setTimeout(doSearch, 300)
}
async function doSearch() {
  if (!q.value.trim()) { list.value = []; return }
  loading.value = true
  try { list.value = await searchSchools(q.value.trim()) } finally { loading.value = false }
}
function pick(s: School) { picked.value = s }

async function save() {
  if (!picked.value) { ElMessage.warning('先选一所学校'); return }
  await setMySchool(picked.value.id, degree.value)
  ElMessage.success('记好了，之后按你学校的红线算')
  emit('saved')
  emit('update:modelValue', false)
}
async function clearSchool() {
  await setMySchool(null, null)
  ElMessage.success('已清除')
  emit('saved')
  emit('update:modelValue', false)
}

watch(() => props.modelValue, (v) => {
  if (v) { q.value = ''; list.value = []; picked.value = null; degree.value = 'master' }
})
</script>

<template>
  <el-dialog :model-value="modelValue" title="你在哪所学校？" width="440px" @update:model-value="emit('update:modelValue', $event)">
    <el-input v-model="q" placeholder="搜学校名，北航 / 北京航空航天大学都行" clearable @input="onInput" />
    <div class="list" v-loading="loading">
      <div v-for="s in list" :key="s.id" class="item" :class="{ on: picked?.id === s.id }" @click="pick(s)">
        <span class="nm">{{ s.name }}</span>
        <span class="pv">{{ s.province || '' }}</span>
      </div>
      <div v-if="!loading && q && !list.length" class="empty">没搜到，换个说法试试，或先用通用标准</div>
    </div>
    <div class="deg">
      <span class="lbl">你的学位</span>
      <el-radio-group v-model="degree">
        <el-radio-button value="bachelor">本科</el-radio-button>
        <el-radio-button value="master">硕士</el-radio-button>
        <el-radio-button value="phd">博士</el-radio-button>
      </el-radio-group>
    </div>
    <template #footer>
      <el-button link type="danger" @click="clearSchool">清除学校</el-button>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="save">就选它</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.list { margin: 12px 0; max-height: 240px; overflow-y: auto; }
.item { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-radius: 10px; cursor: pointer; }
.item:hover { background: var(--bg-deep); }
.item.on { background: var(--ai-100); }
.item.on .nm { color: var(--ai-700); font-weight: 600; }
.nm { font-size: 14px; }
.pv { font-size: 12px; color: var(--label-secondary); }
.empty { padding: 16px; text-align: center; color: var(--label-secondary); font-size: 13px; }
.deg { display: flex; align-items: center; gap: 12px; }
.deg .lbl { font-size: 13px; color: var(--label-secondary); }
</style>
