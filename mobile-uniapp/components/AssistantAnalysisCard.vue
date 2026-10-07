<script setup>
import { computed } from 'vue'

/*
 * 助手结构化分析卡（product-feature-plan §2.1）
 * tool_result.card 直接渲染，助手文字作「翻译」。三种工具：
 *   explain_paragraph → 段卡：校准概率条 / 疑似来源 / 表层特征 z 值 / 最可疑句
 *   get_task_detail   → 报告卡：AI 率 vs 红线 / 红黄绿段数 / 贡献最大的段
 *   detect_text       → 即时检测卡：概率 + 表层特征
 */
const props = defineProps({
  name: { type: String, required: true },
  data: { type: Object, default: null },
})

const SOURCE_LABEL = { human: '人写', gpt: 'GPT', claude: 'Claude', qwen: '通义千问', deepseek: 'DeepSeek', glm: '智谱', kimi: 'Kimi', ernie: '文心', other: '其它' }

const prob = computed(() => {
  const p = props.data?.calibratedProb
  return p == null ? null : Math.round(Number(p) * 100)
})
const level = computed(() => {
  if (prob.value == null) return 'none'
  return prob.value >= 70 ? 'red' : prob.value >= 40 ? 'yellow' : 'green'
})
const surface = computed(() => (Array.isArray(props.data?.surfaceEvidence) ? props.data.surfaceEvidence : []))
const buckets = computed(() => {
  const b = props.data?.riskBuckets || {}
  return { red: b['red(>=0.7)'] || 0, yellow: b['yellow(0.4-0.7)'] || 0, green: b['green(<0.4)'] || 0 }
})
const rate = computed(() => (props.data?.aiRate == null ? null : Number(props.data.aiRate)))
const over = computed(() => rate.value != null && props.data?.threshold != null && rate.value > Number(props.data.threshold))
</script>

<template>
  <!-- 段卡 -->
  <view v-if="name === 'explain_paragraph' && data" class="card">
    <view v-if="data.excluded" class="card-head">
      <text class="card-title">第 {{ data.paragraphIdx + 1 }} 段 · 非正文</text>
      <text class="card-sub">{{ data.note }}</text>
    </view>
    <template v-else>
      <view class="card-head">
        <text class="card-title">第 {{ data.paragraphIdx + 1 }} 段 · {{ data.verdict }}</text>
        <text v-if="data.sourceLabel && data.sourceLabel !== 'human'" class="card-tag">疑似 {{ SOURCE_LABEL[data.sourceLabel] || data.sourceLabel }}</text>
      </view>
      <view class="prob-row">
        <text class="prob-label">校准概率</text>
        <view class="prob-bar"><view class="prob-fill" :class="level" :style="{ width: (prob || 0) + '%' }" /></view>
        <text class="prob-val" :class="level">{{ prob == null ? '—' : prob + '%' }}</text>
      </view>
      <text v-if="data.reliability" class="card-warn">{{ data.reliability }}</text>
      <view v-if="surface.length" class="feat">
        <text class="feat-title">表层特征</text>
        <view v-for="f in surface" :key="f.feature" class="feat-row">
          <text class="feat-name">{{ f.feature }}</text>
          <text class="feat-z" :class="f.zscore > 0 ? 'pos' : 'neg'">z={{ f.zscore > 0 ? '+' : '' }}{{ f.zscore }}</text>
          <text class="feat-read">{{ f.reading }}</text>
        </view>
      </view>
      <text v-else-if="typeof data.surfaceEvidence === 'string'" class="card-sub">{{ data.surfaceEvidence }}</text>
      <view v-if="data.sentences?.length" class="sents">
        <text class="feat-title">最可疑的句子</text>
        <view v-for="s in data.sentences" :key="s.idx" class="sent-row">
          <text class="sent-prob">{{ Math.round((s.aiProb || 0) * 100) }}%</text>
          <text class="sent-text">{{ s.text }}…</text>
        </view>
      </view>
    </template>
  </view>

  <!-- 报告卡 -->
  <view v-else-if="name === 'get_task_detail' && data" class="card">
    <view class="card-head">
      <text class="card-title">整体 AI 率</text>
      <text class="card-tag" :class="over ? 'bad' : 'ok'">{{ over ? '超过红线' : '低于红线' }}</text>
    </view>
    <view class="rate-row">
      <text class="rate-big" :class="over ? 'bad' : 'ok'">{{ rate == null ? '—' : rate.toFixed(1) + '%' }}</text>
      <text class="rate-sub">红线 ≤ {{ data.threshold }}% · 正文 {{ data.bodyParagraphs }} 段<template v-if="data.parentAiRate != null">，上次 {{ Number(data.parentAiRate).toFixed(1) }}%</template></text>
    </view>
    <view class="buckets">
      <view class="bucket red"><text>红 {{ buckets.red }}</text></view>
      <view class="bucket yellow"><text>黄 {{ buckets.yellow }}</text></view>
      <view class="bucket green"><text>绿 {{ buckets.green }}</text></view>
    </view>
    <view v-if="data.topRiskParagraphs?.length" class="sents">
      <text class="feat-title">贡献最大的段</text>
      <view v-for="p in data.topRiskParagraphs" :key="p.idx" class="sent-row">
        <text class="sent-prob">段 {{ p.idx + 1 }} · {{ Math.round((p.calibratedProb || 0) * 100) }}%</text>
        <text class="sent-text">{{ p.preview }}…</text>
      </view>
    </view>
  </view>

  <!-- 即时检测卡 -->
  <view v-else-if="name === 'detect_text' && data" class="card">
    <view class="card-head">
      <text class="card-title">即时检测 · {{ data.verdict }}</text>
      <text class="card-sub">{{ data.chars }} 字</text>
    </view>
    <view class="prob-row">
      <text class="prob-label">校准概率</text>
      <view class="prob-bar"><view class="prob-fill" :class="level" :style="{ width: (prob || 0) + '%' }" /></view>
      <text class="prob-val" :class="level">{{ prob == null ? '—' : prob + '%' }}</text>
    </view>
    <text v-if="data.warning" class="card-warn">{{ data.warning }}</text>
    <view v-if="surface.length" class="feat">
      <view v-for="f in surface" :key="f.feature" class="feat-row">
        <text class="feat-name">{{ f.feature }}</text>
        <text class="feat-z" :class="f.zscore > 0 ? 'pos' : 'neg'">z={{ f.zscore > 0 ? '+' : '' }}{{ f.zscore }}</text>
        <text class="feat-read">{{ f.reading }}</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.card {
  margin: $sp-1 0 $sp-2;
  padding: $sp-3;
  border-radius: $radius-md;
  background: $bg-grouped-primary;
  border: $stroke-hairline solid $separator;
}
.card-head { display: flex; align-items: center; justify-content: space-between; gap: $sp-2; margin-bottom: $sp-2; }
.card-title { font-size: $fs-footnote; font-weight: $fw-semibold; color: $label-primary; }
.card-sub { font-size: $fs-caption-2; color: $label-secondary; }
.card-tag {
  font-size: $fs-caption-2; padding: 2rpx $sp-2; border-radius: $radius-xs;
  background: $warning-bg; color: $warning-fg;
  &.bad { background: $danger-bg; color: $danger-fg; }
  &.ok { background: $success-bg; color: $success-fg; }
}
.card-warn { display: block; font-size: $fs-caption-2; color: $warning-fg; margin-top: $sp-1; }

.prob-row { display: flex; align-items: center; gap: $sp-2; }
.prob-label { flex: none; font-size: $fs-caption-1; color: $label-secondary; }
.prob-bar { flex: 1; height: 14rpx; border-radius: $radius-pill; background: $fill-tertiary; overflow: hidden; }
.prob-fill { height: 100%; border-radius: $radius-pill; &.red { background: $danger-solid; } &.yellow { background: $warning-solid; } &.green { background: $success-solid; } }
.prob-val { flex: none; font-size: $fs-footnote; font-weight: $fw-bold; font-variant-numeric: tabular-nums; &.red { color: $danger-fg; } &.yellow { color: $warning-fg; } &.green { color: $success-fg; } }

.feat { margin-top: $sp-2; }
.feat-title { display: block; font-size: $fs-caption-2; color: $label-secondary; margin-bottom: 4rpx; }
.feat-row { display: flex; align-items: baseline; gap: $sp-2; padding: 4rpx 0; }
.feat-name { flex: none; font-size: $fs-caption-1; color: $label-primary; }
.feat-z { flex: none; font-size: $fs-caption-2; font-family: $font-family-mono; &.pos { color: $danger-fg; } &.neg { color: $info-fg; } }
.feat-read { flex: 1; font-size: $fs-caption-1; color: $label-secondary; }

.sents { margin-top: $sp-2; }
.sent-row { display: flex; align-items: baseline; gap: $sp-2; padding: 4rpx 0; }
.sent-prob { flex: none; font-size: $fs-caption-2; font-weight: $fw-semibold; color: $danger-fg; font-variant-numeric: tabular-nums; }
.sent-text { flex: 1; font-size: $fs-caption-1; color: $label-secondary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }

.rate-row { display: flex; align-items: baseline; gap: $sp-2; }
.rate-big { font-size: $fs-title-2; font-weight: $fw-bold; letter-spacing: -1rpx; &.bad { color: $danger-fg; } &.ok { color: $success-fg; } }
.rate-sub { font-size: $fs-caption-1; color: $label-secondary; }
.buckets { display: flex; gap: $sp-2; margin-top: $sp-2; }
.bucket {
  flex: 1; text-align: center; font-size: $fs-caption-1; font-weight: $fw-semibold; padding: $sp-1 0; border-radius: $radius-xs;
  &.red { background: $danger-bg; color: $danger-fg; } &.yellow { background: $warning-bg; color: $warning-fg; } &.green { background: $success-bg; color: $success-fg; }
}
</style>
