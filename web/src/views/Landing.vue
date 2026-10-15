<script setup lang="ts">
import ZyIcon from '@/components/ZyIcon.vue'
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const PILLARS = [
  { icon: 'search', title: '可解释', desc: '逐段给出「为什么像 AI」：句长节奏、套话连接词、用词重复度，附具体数值；再定位最可疑的句子。' },
  { icon: 'compass', title: '溯源', desc: '疑似来自哪家大模型（GPT / 通义 / DeepSeek …）。知道像谁，才知道怎么不像。' },
  { icon: 'shield', title: '救误判', desc: '原创被判 AI？助手帮你整理申诉材料与写作过程证明指引，而不是让你花钱「降 AI」。' },
]

const STEPS = [
  { n: '1', title: '上传或粘贴', desc: 'PDF / Word / TXT 整篇上传，或粘贴一段先试试。参考文献、致谢、图表标题自动排除，不冤枉打分。' },
  { n: '2', title: '看懂报告', desc: '整体 AI 率对比你学校的红线，红黄绿分布一眼看清，「先改这几段」按贡献排序。' },
  { n: '3', title: '自己改，再测一次', desc: '问助手「为什么这段像 AI」，拿到方向后自己重写；上传修改稿可逐段对比上次。' },
]

const RESCUE = [
  { title: '先看是哪几段，不是整篇', desc: 'AI 率是校准后的整体比例，多数超线只由两三段贡献。打开报告的「先改这几段」，别急着全文重写。' },
  { title: '弄清楚「为什么像」', desc: '句子长度太匀、「首先 / 其次 / 综上所述」密集、同一批词反复出现，是最常见的三个原因。助手会把数值翻成人话。' },
  { title: '准备过程材料，走申诉', desc: '写作提纲、阶段草稿、文献笔记、导师沟通记录，都是原创证明。平台可一键生成申诉材料，附上争议段落。' },
]

const FAQ = [
  { q: '检测免费吗？', a: '课题阶段完全免费，不限次数。我们不卖「降 AI」服务，也不会推销任何改写产品。' },
  { q: '为什么我自己写的论文会被判 AI？', a: '规范的学术写作本身就有「模板感」：句式工整、连接词固定、术语重复。检测模型看的是统计规律，不是你有没有用 AI。所以我们逐段给出原因，并提供申诉通道。' },
  { q: '你们会帮我改写、降 AI 率吗？', a: '不会。AI 改写等于代笔，学校查出来风险更大。助手只讲原则和方向，告诉你哪段、为什么，由你自己重写。' },
  { q: '结果和学校用的知网 / 维普一致吗？', a: '不同平台模型不同，比例不会完全一样。我们的价值是解释与定位，帮你在提交前看懂并修改；最终以学校的检测与规定为准。' },
  { q: '上传的论文会被保存或泄露吗？', a: '论文只用于本次检测与你本人查看报告，不进入训练集；申诉时是否授权争议段落用于改进模型，由你明确勾选。' },
]

let ld: HTMLScriptElement | null = null
onMounted(() => {
  ld = document.createElement('script')
  ld.type = 'application/ld+json'
  ld.text = JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQ.map((f) => ({ '@type': 'Question', name: f.q, acceptedAnswer: { '@type': 'Answer', text: f.a } })),
  })
  document.head.appendChild(ld)
})
onUnmounted(() => { ld?.remove() })

function go(path: string) { router.push(path) }
</script>

<template>
  <div class="landing">
    <header class="nav">
      <div class="nav-inner">
        <span class="brand">知源</span>
        <nav class="nav-links">
          <a href="#how">怎么用</a><a href="#rescue">被误判了？</a><a href="#faq">常见问题</a><router-link to="/verify">验证报告</router-link>
          <el-button v-if="auth.token" round size="small" @click="go('/dashboard')">进入工作台</el-button>
          <el-button v-else round size="small" @click="go('/login')">登录</el-button>
        </nav>
      </div>
    </header>

    <section class="hero">
      <div class="hero-inner">
        <div class="eyebrow"><ZyIcon name="sparkle" :size="13" />免费 · 不代写 · 被误判有路走</div>
        <h1>看得懂的论文 AI 率检测</h1>
        <p class="lead">不只告诉你 AI 率，还告诉你<b>为什么像、哪一段、怎么改</b>。溯源疑似哪家大模型，原创被误判可直接生成申诉材料。</p>
        <div class="cta">
          <el-button type="primary" size="large" round @click="go('/upload')"><ZyIcon name="search" :size="17" />免费检测我的论文</el-button>
          <el-button size="large" round @click="go('/upload')"><ZyIcon name="pen-line" :size="17" />先贴一段看看</el-button>
        </div>
        <div class="trust"><ZyIcon name="shield" :size="14" />本科 20% / 硕士 15% / 博士 10%，按你学校的红线来 · 教育部 2026 新规口径</div>
        <div class="spark-chips">
          <span class="spark-chip" @click="go('/upload')"><ZyIcon name="search" :size="13" />赶 DDL 前自查</span>
          <span class="spark-chip" @click="go('/upload')"><ZyIcon name="pen-line" :size="13" />导师让我改，改哪里？</span>
          <span class="spark-chip" @click="go('/upload')"><ZyIcon name="shield" :size="13" />答辩前突击查一遍</span>
        </div>
      </div>
      <div class="hero-card" aria-hidden="true">
        <div class="hc-top"><span class="hc-rate">23.4%</span><span class="hc-badge">超线 3.4 pp</span></div>
        <div class="hc-bar"><i style="width: 22%" class="r" /><i style="width: 18%" class="y" /><i style="width: 60%" class="g" /></div>
        <div class="hc-row"><b>先改这几段</b><span>按贡献排序</span></div>
        <div class="hc-item"><span class="hc-n">1</span><span>段 7 · 86% · 疑似 GPT</span></div>
        <div class="hc-item"><span class="hc-n">2</span><span>段 12 · 74% · 句长变化 z −1.6</span></div>
        <div class="hc-item"><span class="hc-n">3</span><span>段 3 · 61% · 套话连接词 ×5</span></div>
        <div class="hc-assist"><ZyIcon name="xiaobai-spark" :size="15" />「这段句子长短很匀、读起来『平』，加一句你自己的实验细节会更像人写」</div>
      </div>
    </section>

    <section class="pillars">
      <div v-for="p in PILLARS" :key="p.title" class="pillar">
        <div class="pillar-icon"><ZyIcon :name="p.icon" :size="22" /></div>
        <h3>{{ p.title }}</h3>
        <p>{{ p.desc }}</p>
      </div>
    </section>

    <section id="how" class="block">
      <h2>三步，从「一个数字」到「知道怎么改」</h2>
      <div class="steps">
        <div v-for="s in STEPS" :key="s.n" class="step">
          <span class="step-n">{{ s.n }}</span>
          <h4>{{ s.title }}</h4>
          <p>{{ s.desc }}</p>
        </div>
      </div>
    </section>

    <section id="rescue" class="block rescue">
      <div class="rescue-head">
        <h2>原创论文被判 AI？先做这 3 件事</h2>
        <p>超标不等于作弊。权威平台只给一个比例，灰产让你花钱洗稿，中间缺的是「看懂」。</p>
      </div>
      <div class="rescue-list">
        <div v-for="(r, i) in RESCUE" :key="r.title" class="rescue-item">
          <span class="rescue-n">{{ i + 1 }}</span>
          <div><h4>{{ r.title }}</h4><p>{{ r.desc }}</p></div>
        </div>
      </div>
      <el-button type="primary" @click="go('/upload')"><ZyIcon name="file-text" :size="16" />上传报告，让小白带你看</el-button>
    </section>

    <section class="block compare">
      <h2>和你能找到的其它方式比</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th></th><th>学校检测平台</th><th>「降 AI」服务</th><th>这里</th></tr></thead>
          <tbody>
            <tr><td>告诉你为什么像 AI</td><td>只给比例</td><td>不解释</td><td class="yes">逐段解释 + 数值</td></tr>
            <tr><td>溯源哪家大模型</td><td>—</td><td>—</td><td class="yes">有</td></tr>
            <tr><td>原创被误判怎么办</td><td>走学校流程</td><td>花钱改写</td><td class="yes">申诉材料 + 过程证明指引</td></tr>
            <tr><td>合规</td><td>合规</td><td class="no">AI 改写 = 代笔</td><td class="yes">只给方向，不改写</td></tr>
            <tr><td>价格</td><td>按次收费</td><td>几十到几百</td><td class="yes">免费</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section id="faq" class="block">
      <h2>常见问题</h2>
      <el-collapse class="faq">
        <el-collapse-item v-for="f in FAQ" :key="f.q" :title="f.q"><p class="faq-a">{{ f.a }}</p></el-collapse-item>
      </el-collapse>
    </section>

    <section class="final">
      <h2>先看懂，再动笔</h2>
      <el-button type="primary" size="large" round @click="go('/upload')"><ZyIcon name="search" :size="17" />免费检测我的论文</el-button>
      <p class="final-sub">检测结果仅供参考，建议人工复核；最终以学校检测与规定为准。</p>
    </section>

    <footer class="foot">论文 AIGC 检测课题组 · 不代写、不改写、不保证通过 · 结果仅供学习与自查</footer>
  </div>
</template>

<style scoped>
.landing { min-height: 100vh; background: var(--system-background); color: var(--label); }
.nav { position: sticky; top: 0; z-index: 10; background: rgba(255, 255, 255, 0.78); backdrop-filter: saturate(180%) blur(20px); -webkit-backdrop-filter: saturate(180%) blur(20px); border-bottom: 1px solid var(--label-quaternary); }
.nav-inner { max-width: 1080px; margin: 0 auto; height: 56px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; }
.brand { font-weight: 700; font-size: 17px; letter-spacing: -0.3px; }
.nav-links { display: flex; align-items: center; gap: 20px; }
.nav-links a { color: var(--label-secondary); text-decoration: none; font-size: 14px; }
.nav-links a.router-link-active { color: var(--label); }
.nav-links a:hover { color: var(--label); }

.hero { max-width: 1080px; margin: 0 auto; padding: 72px 24px 48px; display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr); gap: 48px; align-items: center; }
.eyebrow { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; letter-spacing: .6px; color: var(--ai-700); background: var(--ai-100); padding: 5px 12px; border-radius: 99px; }
h1 { font-size: 46px; line-height: 1.12; letter-spacing: -1.2px; margin: 18px 0 14px; font-weight: 700; }
.lead { font-size: 18px; line-height: 1.6; color: var(--label-secondary); margin: 0 0 24px; }
.lead b { color: var(--label); font-weight: 600; }
.cta { display: flex; gap: 12px; flex-wrap: wrap; }
.trust { margin-top: 18px; font-size: 13px; color: var(--label-secondary); display: flex; align-items: center; gap: 6px; } .trust .zy-icon { color: var(--system-green); }
.spark-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
.spark-chip { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; border-radius: 99px; background: #fff; border: 1px solid var(--separator); font-size: 13px; color: var(--label-secondary); cursor: pointer; transition: background var(--dur-fast); } .spark-chip .zy-icon { color: var(--ai-700); } .spark-chip:hover { background: var(--ai-100); color: var(--ai-700); }

.hero-card { background: #fff; border-radius: 18px; padding: 22px; border: 1px solid rgba(23, 24, 28, 0.06); box-shadow: var(--shadow-lift); font-size: 13px; }
.hc-top { display: flex; align-items: baseline; gap: 10px; }
.hc-rate { font-size: 40px; font-weight: 700; letter-spacing: -1px; color: var(--system-red); font-variant-numeric: tabular-nums; }
.hc-badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 99px; background: rgba(229, 72, 77, 0.12); color: var(--danger-fg); }
.hc-bar { display: flex; height: 8px; border-radius: 99px; overflow: hidden; margin: 12px 0 16px; background: rgba(23, 24, 28, 0.12); }
.hc-bar i { height: 100%; } .hc-bar .r { background: var(--system-red); } .hc-bar .y { background: var(--system-orange); } .hc-bar .g { background: var(--system-green); }
.hc-row { display: flex; justify-content: space-between; margin-bottom: 6px; } .hc-row span { color: var(--label-tertiary); font-size: 12px; }
.hc-item { display: flex; align-items: center; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--label-quaternary); }
.hc-n { width: 20px; height: 20px; border-radius: 50%; background: var(--system-red); color: #fff; font-size: 11px; font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.hc-assist { margin-top: 12px; padding: 10px 12px; border-radius: 10px; background: var(--ai-100); color: var(--ai-700); line-height: 1.5; display: flex; gap: 6px; align-items: flex-start; } .hc-assist .zy-icon { margin-top: 2px; }

.pillars { max-width: 1080px; margin: 0 auto; padding: 16px 24px 48px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.pillar { background: #fff; border-radius: 16px; padding: 22px; box-shadow: 0 2px 12px rgba(23, 24, 28, 0.04); }
.pillar-icon { width: 40px; height: 40px; border-radius: 12px; background: var(--ai-100); color: var(--ai-700); display: grid; place-items: center; }
.pillar h3 { margin: 10px 0 6px; font-size: 18px; }
.pillar p { margin: 0; color: var(--label-secondary); line-height: 1.6; font-size: 14px; }

.block { max-width: 1080px; margin: 0 auto; padding: 40px 24px; }
.block h2 { font-size: 28px; letter-spacing: -0.6px; margin: 0 0 24px; }
.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.step { position: relative; padding: 20px 20px 20px 56px; background: #fff; border-radius: 16px; box-shadow: 0 2px 12px rgba(23, 24, 28, 0.04); }
.step-n { position: absolute; left: 18px; top: 20px; width: 26px; height: 26px; border-radius: 50%; background: var(--label); color: #fff; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; justify-content: center; }
.step h4 { margin: 0 0 6px; font-size: 16px; } .step p { margin: 0; color: var(--label-secondary); font-size: 14px; line-height: 1.6; }

.rescue { background: #fff; border-radius: 24px; margin-top: 8px; margin-bottom: 8px; }
.rescue-head p { color: var(--label-secondary); margin: -12px 0 24px; font-size: 15px; }
.rescue-list { display: flex; flex-direction: column; gap: 14px; margin-bottom: 24px; }
.rescue-item { display: flex; gap: 14px; align-items: flex-start; }
.rescue-n { flex: none; width: 30px; height: 30px; border-radius: 50%; background: rgba(229, 72, 77, 0.12); color: var(--danger-fg); font-weight: 700; display: inline-flex; align-items: center; justify-content: center; }
.rescue-item h4 { margin: 4px 0 4px; font-size: 16px; } .rescue-item p { margin: 0; color: var(--label-secondary); line-height: 1.6; font-size: 14px; }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 16px; overflow: hidden; font-size: 14px; }
th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid var(--label-quaternary); }
th { font-size: 12px; color: var(--label-secondary); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }
td:first-child { font-weight: 600; } td.yes { color: var(--success-fg); font-weight: 600; } td.no { color: var(--danger-fg); }

.faq { background: #fff; border-radius: 16px; padding: 4px 20px; }
.faq-a { margin: 0; color: var(--label-secondary); line-height: 1.7; }

.final { text-align: center; padding: 56px 24px 40px; }
.final h2 { font-size: 30px; margin: 0 0 18px; letter-spacing: -0.6px; }
.final-sub { margin-top: 14px; font-size: 13px; color: var(--label-tertiary); }
.foot { text-align: center; padding: 20px 24px 40px; font-size: 12px; color: var(--label-tertiary); border-top: 1px solid var(--label-quaternary); }

@media (max-width: 860px) {
  .hero { grid-template-columns: 1fr; padding-top: 48px; } h1 { font-size: 34px; }
  .pillars, .steps { grid-template-columns: 1fr; }
  .nav-links a { display: none; }
}
</style>
