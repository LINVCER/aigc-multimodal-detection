<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getSharedReport } from '@/api/detect'
import type { SharedReport } from '@/api/types'

/**
 * 只读分享报告页 /s/:token（公开，不需登录）
 *   顶部提示条：只读 · 有效期 · 浏览次数；全页斜向水印；底部引导「免费检测我的论文」
 *   不提供申诉 / 助手 / 下载 / 修改稿等任何写操作入口
 */
const props = defineProps<{ token: string }>()
const router = useRouter()

const data = ref<SharedReport | null>(null)
const loading = ref(true)
const error = ref('')

const SOURCE_LABEL: Record<string, string> = { human: '人类', gpt: 'GPT', claude: 'Claude', qwen: '通义千问', deepseek: 'DeepSeek', glm: '智谱GLM', kimi: 'Kimi', ernie: '文心', other: '其他' }
const EXCLUDE_LABEL: Record<string, string> = { reference: '参考文献', acknowledgement: '致谢', appendix: '附录', sectionTitle: '章节标题', caption: '图表标题' }
const SCENARIO_LABEL: Record<string, string> = { academic_bachelor: '本科论文', academic_master: '硕士论文', academic_phd: '博士论文', job_report: '职业报告', self_media: '自媒体', other: '其他' }

onMounted(async () => {
  try { data.value = await getSharedReport(props.token) }
  catch (e: any) { error.value = e?.message || '链接无效' }
  finally { loading.value = false }
})

const pass = computed(() => !!(data.value && data.value.aiRate != null && data.value.aiRate <= data.value.threshold))
const color = computed(() => {
  const d = data.value
  if (!d || d.aiRate == null) return 'var(--label-tertiary)'
  return d.aiRate <= d.threshold ? 'var(--system-green)' : d.aiRate <= d.threshold * 1.5 ? 'var(--system-orange)' : 'var(--system-red)'
})
const body = computed(() => (data.value?.paragraphs || []).filter((p) => !p.excluded))
const dist = computed(() => {
  const ps = body.value
  const high = ps.filter((p) => (p.calibratedProb || 0) >= 0.7).length
  const mid = ps.filter((p) => { const v = p.calibratedProb || 0; return v >= 0.4 && v < 0.7 }).length
  const n = Math.max(1, ps.length)
  return { high, mid, low: ps.length - high - mid, hp: (high / n) * 100, mp: (mid / n) * 100, lp: ((ps.length - high - mid) / n) * 100 }
})
const sources = computed(() => Object.entries(data.value?.sourceLabels || {}).sort(([, a], [, b]) => b - a))
const watermarkCells = Array.from({ length: 60 })
const probColor = (p: number) => (p >= 0.7 ? 'var(--system-red)' : p >= 0.4 ? 'var(--system-orange)' : 'var(--system-green)')
const sentenceBg = (p: number) => (p >= 0.7 ? 'rgba(255, 59, 48, 0.14)' : p >= 0.4 ? 'rgba(255, 149, 0, 0.16)' : 'transparent')
const fmt = (s?: string | null) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')
</script>

<template>
  <div class="shared">
    <div class="watermark" aria-hidden="true"><span v-for="(_, i) in watermarkCells" :key="i">{{ data?.watermark || '知源 · 只读分享' }}</span></div>

    <header class="bar">
      <span class="bar-brand" @click="router.push('/')">知源</span>
      <span class="bar-tag">只读分享</span>
      <span v-if="data" class="bar-meta">有效期至 {{ fmt(data.expiresAt) }} · 已查看 {{ data.viewCount }} 次</span>
    </header>

    <main class="main">
      <div v-if="loading" class="state">加载中…</div>
      <div v-else-if="error" class="state">
        <div class="state-title">这个分享链接打不开</div>
        <div class="state-sub">{{ error }}</div>
        <el-button type="primary" round @click="router.push('/')">去知源免费检测</el-button>
      </div>

      <template v-else-if="data">
        <el-card class="hero" body-style="padding: 28px 32px">
          <div class="hero-top">
            <div>
              <div class="eyebrow">{{ SCENARIO_LABEL[data.scenario] || data.scenario }} · 红线 {{ data.threshold }}%</div>
              <h1 class="title">{{ data.paperTitle }}</h1>
              <div class="meta">检测时间 {{ fmt(data.detectedAt) }} · 模型 {{ data.modelVersion || '—' }} · {{ data.wordCount || '—' }} 字<template v-if="data.reportNo"> · 报告编号 {{ data.reportNo }}（<router-link to="/verify" class="meta-link">验证真伪</router-link>）</template></div>
            </div>
            <div class="rate-box">
              <div class="rate" :style="{ color }">{{ data.aiRate?.toFixed(1) }}<span>%</span></div>
              <div class="verdict" :class="pass ? 'ok' : 'bad'">{{ pass ? '低于红线' : '超过红线' }}</div>
            </div>
          </div>
          <div class="dist">
            <div class="dist-bar"><i class="h" :style="{ width: dist.hp + '%' }" /><i class="m" :style="{ width: dist.mp + '%' }" /><i class="l" :style="{ width: dist.lp + '%' }" /></div>
            <div class="dist-legend"><b class="h">高 {{ dist.high }}</b><b class="m">中 {{ dist.mid }}</b><b class="l">低 {{ dist.low }}</b><span class="muted">正文 {{ body.length }} 段<template v-if="data.excludedParagraphCount"> · 排除 {{ data.excludedParagraphCount }}</template></span></div>
          </div>
        </el-card>

        <div class="grid">
          <div class="col">
            <div class="sec">段落分析<span class="sec-sub">句子按 AI 概率着色</span></div>
            <el-card v-for="p in data.paragraphs" :key="p.paragraphIdx" class="para" :class="{ ex: p.excluded }" body-style="padding: 0">
              <div class="para-head">
                <i class="bar-i" :style="{ background: p.excluded ? 'rgba(120,120,128,0.3)' : probColor(p.calibratedProb || 0) }" />
                <span class="idx">段 {{ p.paragraphIdx + 1 }}</span>
                <span v-if="p.excluded" class="ex-badge">未参与计算 · {{ EXCLUDE_LABEL[p.excludeReason || ''] || '非正文' }}</span>
                <b v-else :style="{ color: probColor(p.calibratedProb || 0) }">{{ ((p.calibratedProb || 0) * 100).toFixed(0) }}%<span v-if="p.sourceLabel && p.sourceLabel !== 'human'" class="muted"> · 疑似 {{ SOURCE_LABEL[p.sourceLabel] || p.sourceLabel }}</span></b>
                <span v-if="p.sectionName" class="muted small">{{ p.sectionName }}</span>
              </div>
              <div class="para-body">
                <template v-if="p.excluded"><span class="muted">{{ p.text }}</span></template>
                <template v-else-if="p.sentences?.length"><span v-for="s in p.sentences" :key="s.sentenceIdx" :style="{ background: sentenceBg(s.aiProb) }">{{ s.text }}</span></template>
                <template v-else>{{ p.text }}</template>
              </div>
            </el-card>
          </div>
          <aside class="side">
            <el-card class="side-card" body-style="padding: 16px 18px">
              <div class="side-title">疑似来源分布</div>
              <div v-for="[k, v] in sources" :key="k" class="src"><span>{{ SOURCE_LABEL[k] || k }}</span><b>{{ (v * 100).toFixed(0) }}%</b></div>
              <div v-if="!sources.length" class="muted small">暂无溯源数据</div>
            </el-card>
            <el-card class="side-card cta" body-style="padding: 18px">
              <div class="cta-title">也想看懂自己的论文为什么像 AI？</div>
              <div class="cta-sub">知源逐段解释、溯源哪家大模型、误判可申诉。课题阶段免费，不代写。</div>
              <el-button type="primary" round @click="router.push('/')">免费检测我的论文</el-button>
            </el-card>
            <div class="note">本页为只读分享，内容由报告所有者授权查看。检测结果仅供参考，最终以学校规定为准。</div>
          </aside>
        </div>
      </template>
    </main>
  </div>
</template>

<style scoped>
.shared { position: relative; min-height: 100vh; background: var(--system-background); overflow: hidden; }
.watermark { position: fixed; inset: -20%; z-index: 5; pointer-events: none; display: grid; grid-template-columns: repeat(6, 1fr); gap: 80px 40px; transform: rotate(-24deg); opacity: 0.07; font-size: 16px; font-weight: 600; color: var(--label); user-select: none; }
.watermark span { white-space: nowrap; }
.bar { position: sticky; top: 0; z-index: 10; height: 52px; padding: 0 24px; display: flex; align-items: center; gap: 12px; background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(20px); border-bottom: 1px solid var(--label-quaternary); }
.bar-brand { font-weight: 700; cursor: pointer; }
.bar-tag { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 99px; background: rgba(0, 122, 255, 0.1); color: var(--system-blue); }
.bar-meta { margin-left: auto; font-size: 12px; color: var(--label-secondary); }
.main { position: relative; z-index: 1; max-width: 1080px; margin: 0 auto; padding: 28px 24px 64px; }
.state { text-align: center; padding: 80px 0; color: var(--label-secondary); }
.state-title { font-size: 20px; font-weight: 600; color: var(--label); } .state-sub { margin: 8px 0 20px; }
.hero-top { display: flex; justify-content: space-between; gap: 24px; align-items: flex-start; }
.eyebrow { font-size: 12px; color: var(--label-secondary); letter-spacing: .5px; }
.title { font-size: 24px; letter-spacing: -0.5px; margin: 6px 0 6px; }
.meta { font-size: 12px; color: var(--label-tertiary); } .meta-link { color: var(--system-blue); text-decoration: none; }
.rate-box { text-align: right; flex: none; }
.rate { font-size: 48px; font-weight: 700; letter-spacing: -1.5px; line-height: 1; font-variant-numeric: tabular-nums; } .rate span { font-size: 20px; color: var(--label-secondary); margin-left: 2px; }
.verdict { display: inline-block; margin-top: 8px; padding: 3px 10px; border-radius: 99px; font-size: 12px; font-weight: 600; }
.verdict.ok { background: rgba(52, 199, 89, 0.14); color: #1B7F3E; } .verdict.bad { background: rgba(255, 59, 48, 0.14); color: #C62A22; }
.dist { margin-top: 18px; }
.dist-bar { display: flex; height: 10px; border-radius: 99px; overflow: hidden; background: rgba(120, 120, 128, 0.12); } .dist-bar i { height: 100%; }
.h { color: #C62A22; } .m { color: #B26200; } .l { color: #1B7F3E; }
.dist-bar .h { background: var(--system-red); } .dist-bar .m { background: var(--system-orange); } .dist-bar .l { background: var(--system-green); }
.dist-legend { display: flex; gap: 14px; margin-top: 6px; font-size: 12px; } .dist-legend .muted { margin-left: auto; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 24px; margin-top: 20px; align-items: start; }
@media (max-width: 900px) { .grid { grid-template-columns: 1fr; } .hero-top { flex-direction: column; } .rate-box { text-align: left; } }
.sec { font-size: 12px; font-weight: 500; color: var(--label-secondary); text-transform: uppercase; letter-spacing: .5px; padding: 4px 4px 8px; } .sec-sub { margin-left: 10px; text-transform: none; color: var(--label-tertiary); }
.para { margin-bottom: 10px; overflow: hidden; } .para.ex { opacity: .7; }
.para-head { display: flex; align-items: center; gap: 10px; padding: 10px 16px 10px 0; }
.bar-i { width: 4px; align-self: stretch; margin-right: 6px; border-radius: 0 2px 2px 0; }
.idx { font-size: 11px; font-weight: 600; color: var(--label-secondary); text-transform: uppercase; letter-spacing: .6px; }
.ex-badge { font-size: 12px; color: var(--label-secondary); background: rgba(120, 120, 128, 0.14); padding: 2px 10px; border-radius: 99px; }
.para-body { padding: 0 16px 14px 20px; font-size: 15px; line-height: 1.75; }
.muted { color: var(--label-secondary); } .small { font-size: 12px; }
.side { position: sticky; top: 68px; display: flex; flex-direction: column; gap: 14px; }
.side-title { font-weight: 600; margin-bottom: 8px; }
.src { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--label-quaternary); font-size: 14px; } .src:last-child { border-bottom: none; }
.cta { background: linear-gradient(160deg, #0B1F3A 0%, #10355E 70%); color: #fff; }
.cta-title { font-weight: 600; font-size: 16px; } .cta-sub { font-size: 13px; opacity: .8; margin: 8px 0 14px; line-height: 1.5; }
.note { font-size: 12px; color: var(--label-tertiary); text-align: center; }
</style>
