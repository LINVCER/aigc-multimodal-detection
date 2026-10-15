<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSchoolDetail, type SchoolDetail } from '@/api/school'

const props = defineProps<{ id: string }>()
const router = useRouter()
const detail = ref<SchoolDetail | null>(null)
const loading = ref(true)
const DEG_CN: Record<string, string> = { bachelor: '本科', master: '硕士', phd: '博士' }
const PLAT: Record<string, string> = { cnki: '知网', vip: '维普', wanfang: '万方', gezida: '格子达' }

async function load() {
  loading.value = true
  try {
    detail.value = await getSchoolDetail(Number(props.id))
    if (detail.value) document.title = `${detail.value.name} 毕业论文 AI 率 / 查重要求 · 知源`
  } finally { loading.value = false }
}
onMounted(load)
</script>

<template>
  <div class="wrap" v-loading="loading">
    <template v-if="detail">
      <a class="back" @click="router.push('/schools')">‹ 所有学校</a>
      <h1>{{ detail.name }}</h1>
      <p class="sub">{{ detail.province || '' }} · 学位论文检测红线</p>

      <el-card v-if="detail.rules && detail.rules.length" class="rules">
        <table>
          <thead><tr><th>学位</th><th>AI 率红线</th><th>查重红线</th><th>检测平台</th><th>届别</th><th>来源</th></tr></thead>
          <tbody>
            <tr v-for="(r, i) in detail.rules" :key="i">
              <td>{{ DEG_CN[r.degreeType] || r.degreeType }}<template v-if="r.college"> · {{ r.college }}</template></td>
              <td><b v-if="r.aiRateLimit != null">≤ {{ r.aiRateLimit }}%</b><span v-else class="muted">—</span></td>
              <td><span v-if="r.plagiarismLimit != null">≤ {{ r.plagiarismLimit }}%</span><span v-else class="muted">—</span></td>
              <td>{{ PLAT[r.platform || ''] || r.platform || '—' }}</td>
              <td>{{ r.effectiveYear || '—' }}</td>
              <td><a v-if="r.sourceUrl" :href="r.sourceUrl" target="_blank" class="src">原文</a><span v-else class="muted">—</span></td>
            </tr>
          </tbody>
        </table>
        <p class="note">以学校最新通知为准；AI 率比较的是校准后的整体生成内容比例。</p>
      </el-card>

      <el-card v-else class="empty-rules">
        <p>这所学校的红线还没收录。多数学校的要求在研究生院 / 教务处的通知里，你可以把链接告诉我们，核实后补上。</p>
        <p class="muted">暂时先按教育部通用口径：本科 20% / 硕士 15% / 博士 10%。</p>
      </el-card>

      <div class="cta">
        <el-button type="primary" size="large" round @click="router.push('/upload')">用这个标准测一篇</el-button>
      </div>
    </template>
    <div v-else-if="!loading" class="notfound">没找到这所学校</div>
  </div>
</template>

<style scoped>
.wrap { max-width: 820px; margin: 0 auto; padding: 40px 20px 80px; min-height: 60vh; }
.back { color: var(--label-secondary); font-size: 13px; cursor: pointer; }
h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.4px; margin: 12px 0 4px; }
.sub { color: var(--label-secondary); margin: 0 0 20px; }
.rules table { width: 100%; border-collapse: collapse; font-size: 14px; }
.rules th { text-align: left; font-size: 12px; color: var(--label-secondary); font-weight: 500; padding: 8px 10px; border-bottom: 1px solid var(--separator); text-transform: uppercase; letter-spacing: 0.4px; }
.rules td { padding: 12px 10px; border-bottom: 1px solid var(--separator); }
.rules td b { color: var(--danger-fg); }
.muted { color: var(--label-tertiary); }
.src { color: var(--ai-700); font-weight: 600; }
.note { font-size: 12px; color: var(--label-secondary); margin: 14px 0 0; }
.empty-rules p { margin: 0 0 8px; line-height: 1.6; }
.cta { text-align: center; margin-top: 32px; }
.notfound { text-align: center; color: var(--label-secondary); padding: 60px; }
</style>
