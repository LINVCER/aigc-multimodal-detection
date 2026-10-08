<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { verifyReport } from '@/api/detect'
import type { ReportVerify } from '@/api/types'

/**
 * 报告真伪验证（公开页）
 *   /verify            手动输入编号 + 验证码
 *   /verify/ZY-…?code= 扫 PDF 二维码直达，自动验证
 */
const props = defineProps<{ reportNo?: string }>()
const route = useRoute()
const router = useRouter()

const reportNo = ref((props.reportNo || '').toUpperCase())
const code = ref(String(route.query.code || '').toUpperCase())
const loading = ref(false)
const result = ref<ReportVerify | null>(null)
const error = ref('')

const SCENARIO_LABEL: Record<string, string> = { academic_bachelor: '本科论文', academic_master: '硕士论文', academic_phd: '博士论文', job_report: '职业报告', self_media: '自媒体', other: '其他' }
const fmt = (s?: string | null) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')
const normNo = (v: string) => v.trim().toUpperCase().replace(/\s+/g, '')

async function doVerify() {
  error.value = ''
  result.value = null
  const no = normNo(reportNo.value)
  const c = code.value.trim().toUpperCase()
  if (!no || !c) { error.value = '请输入报告编号和验证码'; return }
  loading.value = true
  try { result.value = await verifyReport(no, c) }
  catch (e: any) { error.value = e?.message || '验证失败，请稍后再试' }
  finally { loading.value = false }
}
function resetForm() { result.value = null; error.value = ''; code.value = ''; router.replace('/verify') }

onMounted(() => { if (reportNo.value && code.value) doVerify() })
</script>

<template>
  <div class="verify">
    <header class="bar"><router-link to="/" class="bar-brand"><img src="/logo-mark.png" alt="" class="bar-logo" />知源</router-link><span class="bar-title">验证报告真伪</span><span /></header>

    <main class="main">
      <div class="intro">
        <h1>验证检测报告</h1>
        <p>每份知源检测报告在完成时都会签发唯一的报告编号、验证码和服务端签名。输入 PDF 封面上的编号与验证码，即可核对这份报告是否由知源签发、内容是否被改动。</p>
      </div>

      <el-card class="form-card" body-style="padding: 24px">
        <form @submit.prevent="doVerify">
          <div class="fld"><span class="fld-label">报告编号</span><el-input v-model="reportNo" placeholder="ZY-20261008-XXXXXX" size="large" clearable @input="(v: string) => (reportNo = v.toUpperCase())" /></div>
          <div class="fld"><span class="fld-label">验证码</span><el-input v-model="code" placeholder="PDF 封面 8 位验证码" size="large" maxlength="8" clearable @input="(v: string) => (code = v.toUpperCase())" /></div>
          <div v-if="error" class="err">{{ error }}</div>
          <el-button type="primary" size="large" round native-type="submit" :loading="loading" style="width: 100%">验 证</el-button>
        </form>
      </el-card>

      <transition name="drop">
        <el-card v-if="result" class="result" :class="result.valid ? (result.signatureValid ? 'ok' : 'warn') : 'bad'" body-style="padding: 24px">
          <div class="result-head">
            <span class="shield">{{ result.valid ? (result.signatureValid ? '✓' : '!') : '✕' }}</span>
            <div>
              <div class="result-title">{{ result.valid ? (result.signatureValid ? '报告真实有效' : '编号有效，但内容已变动') : '验证未通过' }}</div>
              <div class="result-sub">{{ result.message }}</div>
            </div>
          </div>
          <template v-if="result.valid">
            <dl class="kv">
              <dt>报告编号</dt><dd><code>{{ result.reportNo }}</code></dd>
              <dt>论文标题</dt><dd>{{ result.paperTitle || '—' }}</dd>
              <dt>检测结论</dt><dd><b :class="result.pass ? 'g' : 'r'">{{ result.aiRate?.toFixed(1) }}%</b> <span class="muted">· 红线 {{ result.threshold }}% · {{ result.pass ? '达标' : '超线' }} · {{ SCENARIO_LABEL[result.scenario || ''] || result.scenario }}</span></dd>
              <dt>检测时间</dt><dd>{{ fmt(result.detectedAt) }}</dd>
              <dt>签发时间</dt><dd>{{ fmt(result.signedAt) }}</dd>
              <dt>模型</dt><dd>{{ result.modelVersion || '—' }}<span class="muted"> · {{ result.wordCount || '—' }} 字 · 正文 {{ result.bodyParagraphCount ?? '—' }} 段</span></dd>
              <dt>签名指纹</dt><dd><code class="fp">{{ result.fingerprint || '—' }}</code><span class="muted small"> 应与 PDF 封面一致</span></dd>
              <dt>被验证</dt><dd>{{ result.verifyCount }} 次</dd>
            </dl>
            <div v-if="!result.signatureValid" class="warn-note">签名重算与签发时不一致：报告完成后结果数据被修改过，或服务端签名密钥已更换。请以知源平台内的在线报告为准。</div>
          </template>
          <div class="result-foot"><el-button link @click="resetForm">验证另一份</el-button><span class="muted small">验证结果只展示摘要，不含论文正文。</span></div>
        </el-card>
      </transition>

      <div class="how">
        <h3>怎么核对</h3>
        <ol>
          <li>编号与验证码印在 PDF 报告封面「报告溯源凭证」区域，也可在知源结果页复制。</li>
          <li>扫描 PDF 上的二维码会直接打开本页并自动验证。</li>
          <li>验证页显示的「签名指纹」应与 PDF 上一致；不一致说明 PDF 被改过。</li>
          <li>验证通过只说明报告由知源签发且内容未变，检测结论本身仍以学校规定为准。</li>
        </ol>
      </div>
    </main>
  </div>
</template>

<style scoped>
.verify { min-height: 100vh; background: var(--system-background); }
.bar { position: sticky; top: 0; z-index: 10; height: 56px; padding: 0 24px; display: flex; align-items: center; justify-content: space-between; background: rgba(255, 255, 255, 0.85); backdrop-filter: blur(20px); border-bottom: 1px solid var(--label-quaternary); }
.bar-brand { display: inline-flex; align-items: center; gap: 8px; font-weight: 700; color: var(--label); text-decoration: none; } .bar-logo { width: 24px; height: 24px; object-fit: contain; }
.bar-title { font-weight: 600; }
.main { max-width: 560px; margin: 0 auto; padding: 40px 24px 64px; display: flex; flex-direction: column; gap: 20px; }
.intro h1 { font-size: 28px; letter-spacing: -0.6px; margin: 0 0 8px; } .intro p { color: var(--label-secondary); line-height: 1.7; margin: 0; }
.fld { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; } .fld-label { font-size: 13px; color: var(--label-secondary); font-weight: 500; }
.err { color: var(--system-red); font-size: 13px; margin: -6px 0 12px; }
.result { border: 1px solid transparent; } .result.ok { border-color: rgba(52, 199, 89, 0.5); } .result.warn { border-color: rgba(255, 149, 0, 0.6); } .result.bad { border-color: rgba(255, 59, 48, 0.5); }
.result-head { display: flex; align-items: center; gap: 14px; }
.shield { width: 48px; height: 48px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 700; color: #fff; flex: none; }
.ok .shield { background: var(--system-green); } .warn .shield { background: var(--system-orange); } .bad .shield { background: var(--system-red); }
.result-title { font-size: 18px; font-weight: 700; } .result-sub { font-size: 13px; color: var(--label-secondary); margin-top: 2px; }
.kv { display: grid; grid-template-columns: 76px 1fr; gap: 10px 12px; margin: 18px 0 0; font-size: 14px; padding-top: 16px; border-top: 1px solid var(--label-quaternary); }
.kv dt { color: var(--label-secondary); } .kv dd { margin: 0; } .kv code { font-weight: 600; letter-spacing: .5px; } .fp { font-size: 12px; }
.g { color: #1B7F3E; } .r { color: #C62A22; } .muted { color: var(--label-secondary); } .small { font-size: 12px; }
.warn-note { margin-top: 14px; padding: 10px 12px; border-radius: 10px; background: rgba(255, 149, 0, 0.1); color: #B26200; font-size: 13px; line-height: 1.5; }
.result-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; }
.how h3 { font-size: 15px; margin: 8px 0 8px; } .how ol { margin: 0; padding-left: 20px; color: var(--label-secondary); line-height: 1.8; font-size: 14px; }
.drop-enter-active { transition: all .25s ease; } .drop-enter-from { opacity: 0; transform: translateY(-6px); }
</style>
