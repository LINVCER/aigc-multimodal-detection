<script setup>
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { verifyReport } from '@/api/detect'

/*
 * 验证报告真伪（公开页，不需登录）
 *   手动输入编号 + 验证码；小程序可扫 PDF 二维码直填（解析 /verify/{no}?code=）
 *   结果只展示摘要，不含论文正文
 */
const reportNo = ref('')
const code = ref('')
const loading = ref(false)
const result = ref(null)
const error = ref('')

const SCENARIO_LABEL = { academic_bachelor: '本科论文', academic_master: '硕士论文', academic_phd: '博士论文', job_report: '职业报告', self_media: '自媒体', other: '其他' }
const fmt = (s) => (s ? String(s).replace('T', ' ').slice(0, 16) : '—')

function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/home/home' })
}

async function doVerify() {
  error.value = ''
  result.value = null
  const no = reportNo.value.trim().toUpperCase().replace(/\s+/g, '')
  const c = code.value.trim().toUpperCase()
  if (!no || !c) { error.value = '请输入报告编号和验证码'; return }
  loading.value = true
  try { result.value = await verifyReport(no, c) }
  catch (e) { error.value = e?.message || '验证失败，请稍后再试' }
  finally { loading.value = false }
}

/** 从二维码 / 链接里解析编号与验证码 */
function fillFromText(text) {
  const m = String(text || '').match(/verify\/([A-Z0-9-]+)\?code=([A-Z0-9]+)/i)
  if (m) { reportNo.value = m[1].toUpperCase(); code.value = m[2].toUpperCase(); return true }
  const n = String(text || '').match(/(ZY-\d{8}-[A-Z0-9]{6})/i)
  if (n) { reportNo.value = n[1].toUpperCase(); return true }
  return false
}
function onScan() {
  uni.scanCode({
    onlyFromCamera: false,
    success: (res) => { if (fillFromText(res.result)) doVerify(); else uni.showToast({ title: '二维码不是知源报告', icon: 'none' }) },
    fail: () => {},
  })
}
function pasteCred() {
  uni.getClipboardData({ success: (res) => { if (fillFromText(res.data)) { uni.showToast({ title: '已识别', icon: 'none' }) } else { uni.showToast({ title: '剪贴板里没有报告编号', icon: 'none' }) } } })
}
function resetForm() { result.value = null; error.value = ''; code.value = '' }

onLoad((q) => {
  if (q && q.reportNo) reportNo.value = String(q.reportNo).toUpperCase()
  if (q && q.code) code.value = String(q.code).toUpperCase()
  if (reportNo.value && code.value) doVerify()
})
</script>

<template>
  <view class="page">
    <view class="nav">
      <text class="nav-back" @click="goBack">‹</text>
      <text class="nav-title">验证报告真伪</text>
      <text class="nav-side" />
    </view>

    <view class="intro">
      <text class="intro-title">验证检测报告</text>
      <text class="intro-sub">每份知源报告完成时都签发唯一编号、验证码和服务端签名。输入 PDF 封面上的编号与验证码，核对报告是否由知源签发、内容是否被改动。</text>
    </view>

    <view class="card">
      <view class="fld">
        <text class="fld-label">报告编号</text>
        <input v-model="reportNo" class="inp" placeholder="ZY-20261008-XXXXXX" placeholder-style="color: rgba(60,60,67,0.30)" :adjust-position="true" :cursor-spacing="24" @input="(e) => (reportNo = String(e.detail.value).toUpperCase())" />
      </view>
      <view class="fld">
        <text class="fld-label">验证码</text>
        <input v-model="code" class="inp" placeholder="PDF 封面 8 位验证码" maxlength="8" placeholder-style="color: rgba(60,60,67,0.30)" :adjust-position="true" :cursor-spacing="24" @input="(e) => (code = String(e.detail.value).toUpperCase())" />
      </view>
      <text v-if="error" class="err">{{ error }}</text>
      <button class="submit" :loading="loading" :disabled="loading" @click="doVerify">验 证</button>
      <view class="helpers">
        <!-- #ifdef MP-WEIXIN || APP-PLUS -->
        <text class="helper" @click="onScan">扫 PDF 二维码</text>
        <!-- #endif -->
        <text class="helper" @click="pasteCred">从剪贴板识别</text>
      </view>
    </view>

    <view v-if="result" class="result" :class="result.valid ? (result.signatureValid ? 'ok' : 'warn') : 'bad'">
      <view class="result-head">
        <view class="shield"><text>{{ result.valid ? (result.signatureValid ? '✓' : '!') : '✕' }}</text></view>
        <view class="result-text">
          <text class="result-title">{{ result.valid ? (result.signatureValid ? '报告真实有效' : '编号有效，但内容已变动') : '验证未通过' }}</text>
          <text class="result-sub">{{ result.message }}</text>
        </view>
      </view>
      <template v-if="result.valid">
        <view class="kv">
          <view class="kv-row"><text class="k">报告编号</text><text class="v mono">{{ result.reportNo }}</text></view>
          <view class="kv-row"><text class="k">论文标题</text><text class="v">{{ result.paperTitle || '—' }}</text></view>
          <view class="kv-row"><text class="k">检测结论</text><text class="v"><text :class="result.pass ? 'g' : 'r'">{{ Number(result.aiRate).toFixed(1) }}%</text> · 红线 {{ result.threshold }}% · {{ result.pass ? '达标' : '超线' }} · {{ SCENARIO_LABEL[result.scenario] || result.scenario }}</text></view>
          <view class="kv-row"><text class="k">检测时间</text><text class="v">{{ fmt(result.detectedAt) }}</text></view>
          <view class="kv-row"><text class="k">模型</text><text class="v">{{ result.modelVersion || '—' }} · {{ result.wordCount || '—' }} 字</text></view>
          <view class="kv-row"><text class="k">签名指纹</text><text class="v mono">{{ result.fingerprint || '—' }}</text></view>
          <view class="kv-row"><text class="k">被验证</text><text class="v">{{ result.verifyCount }} 次</text></view>
        </view>
        <text v-if="!result.signatureValid" class="warn-note">签名重算与签发时不一致：报告完成后结果被修改过，或服务端密钥已更换。请以知源平台内的在线报告为准。</text>
      </template>
      <text class="result-foot" @click="resetForm">验证另一份 ›</text>
    </view>

    <view class="how">
      <text class="how-title">怎么核对</text>
      <text class="how-item">1. 编号与验证码印在 PDF 封面「报告溯源凭证」区域，也可在知源结果页复制。</text>
      <text class="how-item">2. 验证页显示的「签名指纹」应与 PDF 上一致；不一致说明 PDF 被改过。</text>
      <text class="how-item">3. 验证通过只说明报告由知源签发且内容未变，检测结论本身仍以学校规定为准。</text>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.page { min-height: 100vh; background: $bg-grouped-primary; padding: #{"calc(env(safe-area-inset-top) + 0rpx)"} $sp-4 80rpx; }
.nav { height: 88rpx; margin: 0 (-$sp-4); padding: 0 $sp-4; display: flex; align-items: center; justify-content: space-between; background: $bg-primary; border-bottom: $stroke-hairline solid $separator; }
.nav-back { font-size: 56rpx; color: $brand-primary; line-height: 1; width: 60rpx; }
.nav-title { font-size: $fs-headline; font-weight: $fw-semibold; color: $label-primary; }
.nav-side { width: 60rpx; }
.intro { margin: $sp-5 0 $sp-4; }
.intro-title { display: block; font-size: $fs-title-2; font-weight: $fw-bold; color: $label-primary; }
.intro-sub { display: block; margin-top: $sp-2; font-size: $fs-footnote; color: $label-secondary; line-height: $lh-normal; }
.card { @include card; padding: $sp-4; }
.fld { margin-bottom: $sp-3; }
.fld-label { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-bottom: 8rpx; }
.inp { height: 92rpx; padding: 0 $sp-3; border-radius: $radius-lg; background: $bg-grouped-primary; font-size: $fs-body; color: $label-primary; letter-spacing: 1rpx; }
.err { display: block; font-size: $fs-caption-1; color: $danger-fg; margin: -4rpx 0 $sp-2; }
.submit { height: $size-btn-h-lg; line-height: $size-btn-h-lg; background: $brand-primary; color: #fff; font-size: $fs-headline; font-weight: $fw-semibold; border-radius: $radius-pill; &::after { border: none; } }
.helpers { display: flex; justify-content: center; gap: $sp-5; margin-top: $sp-3; }
.helper { font-size: $fs-footnote; color: $brand-primary; }
.result { @include card; margin-top: $sp-4; padding: $sp-4; border: 2rpx solid transparent; &.ok { border-color: rgba(52, 199, 89, 0.5); } &.warn { border-color: rgba(255, 149, 0, 0.6); } &.bad { border-color: rgba(255, 59, 48, 0.5); } }
.result-head { display: flex; align-items: center; gap: $sp-3; }
.shield { width: 88rpx; height: 88rpx; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex: none; text { color: #fff; font-size: 40rpx; font-weight: $fw-bold; } }
.ok .shield { background: $success-solid; } .warn .shield { background: $warning-solid; } .bad .shield { background: $danger-solid; }
.result-text { flex: 1; min-width: 0; }
.result-title { display: block; font-size: $fs-headline; font-weight: $fw-bold; color: $label-primary; }
.result-sub { display: block; font-size: $fs-caption-1; color: $label-secondary; margin-top: 4rpx; }
.kv { margin-top: $sp-3; padding-top: $sp-3; border-top: $stroke-hairline solid $separator; }
.kv-row { display: flex; gap: $sp-3; padding: 8rpx 0; font-size: $fs-footnote; }
.k { flex: none; width: 140rpx; color: $label-secondary; } .v { flex: 1; min-width: 0; color: $label-primary; word-break: break-all; } .mono { font-weight: $fw-semibold; letter-spacing: 1rpx; }
.g { color: $success-fg; font-weight: $fw-bold; } .r { color: $danger-fg; font-weight: $fw-bold; }
.warn-note { display: block; margin-top: $sp-3; padding: $sp-2 $sp-3; border-radius: $radius-md; background: $warning-bg; color: $warning-fg; font-size: $fs-caption-1; line-height: $lh-normal; }
.result-foot { display: block; margin-top: $sp-3; font-size: $fs-footnote; color: $brand-primary; text-align: right; }
.how { margin-top: $sp-5; }
.how-title { display: block; font-size: $fs-subhead; font-weight: $fw-semibold; color: $label-primary; margin-bottom: $sp-2; }
.how-item { display: block; font-size: $fs-caption-1; color: $label-secondary; line-height: $lh-normal; margin-bottom: 6rpx; }
</style>
