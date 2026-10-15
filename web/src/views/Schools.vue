<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { searchSchools, type School } from '@/api/school'

const router = useRouter()
const q = ref('')
const province = ref('')
const list = ref<School[]>([])
const loading = ref(false)
const PROVINCES = ['北京', '上海', '江苏', '浙江', '广东', '湖北', '陕西', '四川', '山东', '天津']

let timer: ReturnType<typeof setTimeout> | undefined
function onInput() { clearTimeout(timer); timer = setTimeout(load, 300) }
async function load() {
  loading.value = true
  try { list.value = await searchSchools(q.value.trim() || undefined, province.value || undefined) } finally { loading.value = false }
}
function pickProvince(p: string) { province.value = province.value === p ? '' : p; load() }
onMounted(() => {
  document.title = '高校论文 AI 率 / 查重红线查询 · 知源'
  load()
})
</script>

<template>
  <div class="wrap">
    <header class="head">
      <h1>各高校学位论文红线</h1>
      <p>查查你学校对 AIGC 率、查重率的要求。搜不到的学校欢迎告诉我们，核实后收录。</p>
    </header>

    <div class="search">
      <el-input v-model="q" placeholder="搜学校名，北航 / 北京航空航天大学都行" size="large" clearable @input="onInput" />
    </div>
    <div class="provinces">
      <span v-for="p in PROVINCES" :key="p" class="pv" :class="{ on: province === p }" @click="pickProvince(p)">{{ p }}</span>
    </div>

    <div class="grid" v-loading="loading">
      <div v-for="s in list" :key="s.id" class="card" @click="router.push(`/schools/${s.id}`)">
        <div class="nm">{{ s.name }}</div>
        <div class="meta">{{ s.province || '' }}<template v-if="s.shortName"> · {{ s.shortName }}</template></div>
        <div class="go">看红线 ›</div>
      </div>
      <div v-if="!loading && !list.length" class="empty">换个关键词或省份试试</div>
    </div>

    <div class="cta">
      <el-button type="primary" size="large" round @click="router.push('/upload')">用你学校的标准测一篇</el-button>
    </div>
  </div>
</template>

<style scoped>
.wrap { max-width: 920px; margin: 0 auto; padding: 48px 20px 80px; }
.head h1 { font-size: 30px; font-weight: 700; letter-spacing: -0.5px; margin: 0; }
.head p { color: var(--label-secondary); margin: 10px 0 0; }
.search { margin: 24px 0 14px; }
.provinces { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px; }
.pv { padding: 5px 14px; border-radius: 99px; background: #fff; border: 1px solid var(--separator); font-size: 13px; color: var(--label-secondary); cursor: pointer; }
.pv.on { background: var(--ai-100); color: var(--ai-700); border-color: transparent; font-weight: 600; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 14px; min-height: 120px; }
.card { background: #fff; border: 1px solid rgba(23,24,28,0.06); border-radius: 16px; padding: 18px; cursor: pointer; box-shadow: var(--shadow-card); transition: box-shadow .2s; }
.card:hover { box-shadow: var(--shadow-lift); }
.nm { font-size: 15px; font-weight: 600; }
.meta { font-size: 12px; color: var(--label-secondary); margin-top: 6px; }
.go { font-size: 13px; color: var(--ai-700); font-weight: 600; margin-top: 12px; }
.empty { grid-column: 1 / -1; text-align: center; color: var(--label-secondary); padding: 40px; }
.cta { text-align: center; margin-top: 36px; }
</style>
