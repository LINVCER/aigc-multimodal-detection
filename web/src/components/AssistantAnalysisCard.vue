<script setup lang="ts">
import { computed } from 'vue'

/**
 * 助手结构化分析卡（product-feature-plan §2.1）：tool_result.card 直接渲染，助手文字作「翻译」
 */
const props = defineProps<{ name: string; data: any }>()

const SOURCE_LABEL: Record<string, string> = { human: '人写', gpt: 'GPT', claude: 'Claude', qwen: '通义千问', deepseek: 'DeepSeek', glm: '智谱', kimi: 'Kimi', ernie: '文心', other: '其它' }

const prob = computed<number | null>(() => (props.data?.calibratedProb == null ? null : Math.round(Number(props.data.calibratedProb) * 100)))
const level = computed(() => (prob.value == null ? 'none' : prob.value >= 70 ? 'red' : prob.value >= 40 ? 'yellow' : 'green'))
const surface = computed<Array<{ feature: string; zscore: number; reading: string }>>(() => (Array.isArray(props.data?.surfaceEvidence) ? props.data.surfaceEvidence : []))
const buckets = computed(() => {
  const b = props.data?.riskBuckets || {}
  return { red: b['red(>=0.7)'] || 0, yellow: b['yellow(0.4-0.7)'] || 0, green: b['green(<0.4)'] || 0 }
})
const rate = computed<number | null>(() => (props.data?.aiRate == null ? null : Number(props.data.aiRate)))
const over = computed(() => rate.value != null && props.data?.threshold != null && rate.value > Number(props.data.threshold))
const fmtZ = (z: number) => `z=${z > 0 ? '+' : ''}${z}`
const facts = computed<string>(() => {
  const f = props.data?.surfaceFacts
  if (!f || !f.sentences) return ''
  const parts = [`${f.sentences} 句`, `平均 ${f.avgSentLen} 字（${f.sentLenMin}–${f.sentLenMax}）`]
  if (f.discourseMarkers) parts.push(`套话连接词 ${f.discourseMarkers} 处：${(f.discourseMarkerList || []).join('、')}`)
  else parts.push('没有套话连接词')
  return parts.join(' · ')
})
</script>

<template>
  <div v-if="name === 'explain_paragraph' && data" class="card">
    <template v-if="data.excluded">
      <div class="head"><span class="title">第 {{ data.paragraphIdx + 1 }} 段 · 非正文</span><span class="sub">{{ data.note }}</span></div>
    </template>
    <template v-else>
      <div class="head">
        <span class="title">第 {{ data.paragraphIdx + 1 }} 段 · {{ data.verdict }}</span>
        <span v-if="data.sourceLabel && data.sourceLabel !== 'human'" class="tag">疑似 {{ SOURCE_LABEL[data.sourceLabel] || data.sourceLabel }}</span>
      </div>
      <div class="prob"><span class="sub">校准概率</span><div class="bar"><div class="fill" :class="level" :style="{ width: (prob || 0) + '%' }" /></div><b :class="level">{{ prob == null ? '—' : prob + '%' }}</b></div>
      <div v-if="data.reliability" class="warn">{{ data.reliability }}</div>
      <div v-if="surface.length" class="feat">
        <div class="sub">表层特征<template v-if="data.evidenceBasis"> · {{ data.evidenceBasis }}</template></div>
        <div v-for="f in surface" :key="f.feature" class="row"><span class="name">{{ f.feature }}</span><code :class="f.zscore > 0 ? 'pos' : 'neg'">{{ fmtZ(f.zscore) }}</code><span class="read">{{ f.reading }}</span></div>
      </div>
      <div v-else-if="typeof data.surfaceEvidence === 'string'" class="sub">{{ data.surfaceEvidence }}</div>
      <div v-if="facts" class="facts">{{ facts }}</div>
      <div v-if="data.sentences?.length" class="feat">
        <div class="sub">最可疑的句子</div>
        <div v-for="s in data.sentences" :key="s.idx" class="row"><b class="sp">{{ Math.round((s.aiProb || 0) * 100) }}%</b><span class="read ellipsis">{{ s.text }}…</span></div>
      </div>
    </template>
  </div>

  <div v-else-if="name === 'get_task_detail' && data" class="card">
    <div class="head"><span class="title">整体 AI 率</span><span class="tag" :class="over ? 'bad' : 'ok'">{{ over ? '超过红线' : '低于红线' }}</span></div>
    <div class="rate"><b :class="over ? 'bad' : 'ok'">{{ rate == null ? '—' : rate.toFixed(1) + '%' }}</b><span class="sub">红线 ≤ {{ data.threshold }}% · 正文 {{ data.bodyParagraphs }} 段<template v-if="data.parentAiRate != null">，上次 {{ Number(data.parentAiRate).toFixed(1) }}%</template></span></div>
    <div class="buckets"><span class="red">红 {{ buckets.red }}</span><span class="yellow">黄 {{ buckets.yellow }}</span><span class="green">绿 {{ buckets.green }}</span></div>
    <div v-if="data.topRiskParagraphs?.length" class="feat">
      <div class="sub">贡献最大的段</div>
      <div v-for="p in data.topRiskParagraphs" :key="p.idx" class="row"><b class="sp">段 {{ p.idx + 1 }} · {{ Math.round((p.calibratedProb || 0) * 100) }}%</b><span class="read ellipsis">{{ p.preview }}…</span></div>
    </div>
  </div>

  <div v-else-if="name === 'detect_text' && data" class="card">
    <div class="head"><span class="title">即时检测 · {{ data.verdict }}</span><span class="sub">{{ data.chars }} 字</span></div>
    <div class="prob"><span class="sub">校准概率</span><div class="bar"><div class="fill" :class="level" :style="{ width: (prob || 0) + '%' }" /></div><b :class="level">{{ prob == null ? '—' : prob + '%' }}</b></div>
    <div v-if="data.warning" class="warn">{{ data.warning }}</div>
    <div v-if="surface.length" class="feat">
      <div v-if="data.evidenceBasis" class="sub">{{ data.evidenceBasis }}</div>
      <div v-for="f in surface" :key="f.feature" class="row"><span class="name">{{ f.feature }}</span><code :class="f.zscore > 0 ? 'pos' : 'neg'">{{ fmtZ(f.zscore) }}</code><span class="read">{{ f.reading }}</span></div>
    </div>
    <div v-if="facts" class="facts">{{ facts }}</div>
  </div>
</template>

<style scoped lang="scss">
.card { margin: 4px 0 8px; padding: 10px 12px; border-radius: 10px; background: var(--el-fill-color-lighter); border: 1px solid var(--el-border-color-lighter); font-size: 12px; }
.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.title { font-weight: 600; font-size: 13px; }
.sub { color: var(--el-text-color-secondary); font-size: 12px; }
.tag { font-size: 11px; padding: 1px 8px; border-radius: 4px; background: var(--el-color-warning-light-9); color: var(--el-color-warning-dark-2);
  &.bad { background: var(--el-color-danger-light-9); color: var(--el-color-danger-dark-2); }
  &.ok { background: var(--el-color-success-light-9); color: var(--el-color-success-dark-2); } }
.warn { color: var(--el-color-warning-dark-2); margin-top: 4px; }
.prob { display: flex; align-items: center; gap: 8px; }
.bar { flex: 1; height: 7px; border-radius: 99px; background: var(--el-fill-color); overflow: hidden; }
.fill { height: 100%; border-radius: 99px; &.red { background: var(--el-color-danger); } &.yellow { background: var(--el-color-warning); } &.green { background: var(--el-color-success); } }
.prob b { font-variant-numeric: tabular-nums; &.red { color: var(--el-color-danger); } &.yellow { color: var(--el-color-warning-dark-2); } &.green { color: var(--el-color-success-dark-2); } }
.feat { margin-top: 6px; }
.facts { margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--el-border-color-lighter); color: var(--el-text-color-secondary); font-size: 11px; line-height: 1.5; }
.row { display: flex; align-items: baseline; gap: 8px; padding: 2px 0; }
.name { flex: none; }
code { flex: none; font-size: 11px; &.pos { color: var(--el-color-danger); } &.neg { color: var(--el-color-primary); } }
.read { flex: 1; color: var(--el-text-color-secondary); }
.ellipsis { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.sp { flex: none; color: var(--el-color-danger); font-variant-numeric: tabular-nums; }
.rate { display: flex; align-items: baseline; gap: 8px; b { font-size: 22px; letter-spacing: -0.5px; &.bad { color: var(--el-color-danger); } &.ok { color: var(--el-color-success-dark-2); } } }
.buckets { display: flex; gap: 6px; margin-top: 6px; span { flex: 1; text-align: center; padding: 3px 0; border-radius: 4px; font-weight: 600; }
  .red { background: var(--el-color-danger-light-9); color: var(--el-color-danger-dark-2); }
  .yellow { background: var(--el-color-warning-light-9); color: var(--el-color-warning-dark-2); }
  .green { background: var(--el-color-success-light-9); color: var(--el-color-success-dark-2); } }
</style>
