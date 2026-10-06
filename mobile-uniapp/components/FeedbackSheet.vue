<script setup>
import { computed, ref, watch } from 'vue'
import { submitFeedback } from '@/api/feedback'
import { useAuth } from '@/store/auth'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  taskId:  { type: Number, default: 0 },       // 传值 => 锁定 appeal 分类
  defaultCategory: { type: String, default: '' },
  paragraphs: { type: Array, default: () => [] },   // 报告段落，申诉时勾选「哪几段判错了」
})
const emit = defineEmits(['update:modelValue'])
const auth = useAuth()

const category = ref(props.defaultCategory || (props.taskId ? 'appeal' : 'suggestion'))
const content  = ref('')
const contact  = ref('')
const submitting = ref(false)
const pickedIdxs = ref([])
const consentImprove = ref(false)

/* 只列正文里 ≥ 0.5 的段 */
const candidateParas = computed(() =>
  (props.paragraphs || [])
    .filter((p) => !p.excluded && (p.calibratedProb || 0) >= 0.5)
    .map((p) => ({ idx: p.paragraphIdx, prob: Math.round((p.calibratedProb || 0) * 100), preview: (p.text || '').slice(0, 30) })),
)
function togglePara(idx) {
  const i = pickedIdxs.value.indexOf(idx)
  if (i >= 0) pickedIdxs.value.splice(i, 1)
  else pickedIdxs.value.push(idx)
  if (!pickedIdxs.value.length) consentImprove.value = false
}
function toggleConsent() {
  if (!pickedIdxs.value.length) return
  consentImprove.value = !consentImprove.value
}

const canSubmit = computed(() => content.value.trim().length > 0 && content.value.length <= 2000)
const isAppeal  = computed(() => category.value === 'appeal')

watch(() => props.modelValue, (v) => {
  if (v) {
    category.value = props.defaultCategory || (props.taskId ? 'appeal' : 'suggestion')
    content.value = ''
    contact.value = ''
    pickedIdxs.value = []
    consentImprove.value = false
  }
})

function close() { emit('update:modelValue', false) }
// 阻止 sheet 内部滑动/点击穿透到 mask
function noop() {}

async function onSubmit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  try {
    await submitFeedback({
      category: category.value,
      content:  content.value.trim(),
      contact:  contact.value.trim() || undefined,
      taskId:   props.taskId || undefined,
      paragraphIdxs: isAppeal.value && pickedIdxs.value.length ? [...pickedIdxs.value].sort((a, b) => a - b) : undefined,
      consentImprove: isAppeal.value && pickedIdxs.value.length ? consentImprove.value : undefined,
      userId:   auth.userId ? Number(auth.userId) : undefined,
    })
    uni.showToast({ title: '反馈已提交', icon: 'success' })
    close()
  } catch (e) {
    uni.showToast({ title: e?.message || '提交失败', icon: 'none' })
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <view v-if="modelValue" class="fb-mask" @click="close">
    <view class="fb-sheet" @click.stop="noop">
      <view class="fb-handle"></view>
      <view class="fb-header">
        <text class="fb-title">{{ taskId ? '结果申诉' : '意见反馈' }}</text>
        <text class="fb-close" @click="close">✕</text>
      </view>

      <view v-if="!taskId" class="fb-tabs">
        <text
          class="fb-tab" :class="{ active: category === 'suggestion' }"
          @click="category = 'suggestion'"
        >功能建议</text>
        <text
          class="fb-tab" :class="{ active: category === 'bug' }"
          @click="category = 'bug'"
        >问题反馈</text>
      </view>
      <view v-else class="fb-appeal-hint">
        <text>针对任务 #{{ taskId }} 的检测结果申诉，我们会人工复核并回复</text>
      </view>

      <!-- 段级申诉 -->
      <view v-if="isAppeal && candidateParas.length" class="fb-paras">
        <text class="fb-paras-title">哪几段判错了？可多选，不选表示整体申诉</text>
        <scroll-view scroll-y class="fb-paras-scroll">
          <view
            v-for="p in candidateParas" :key="p.idx"
            class="fb-para" :class="{ on: pickedIdxs.includes(p.idx) }"
            @click="togglePara(p.idx)"
          >
            <view class="fb-para-box" :class="{ on: pickedIdxs.includes(p.idx) }">{{ pickedIdxs.includes(p.idx) ? '✓' : '' }}</view>
            <text class="fb-para-tag">第 {{ p.idx + 1 }} 段 · {{ p.prob }}%</text>
            <text class="fb-para-preview">{{ p.preview }}…</text>
          </view>
        </scroll-view>
        <view class="fb-consent" :class="{ off: !pickedIdxs.length }" @click="toggleConsent">
          <view class="fb-para-box" :class="{ on: consentImprove }">{{ consentImprove ? '✓' : '' }}</view>
          <text class="fb-consent-text">同意把勾选段落用于改进检测模型（仅内部评测，不公开、不用于训练；不勾只保留哈希）</text>
        </view>
      </view>

      <textarea
        v-model="content"
        class="fb-textarea"
        :maxlength="2000"
        :cursor-spacing="120"
        :adjust-position="true"
        :placeholder="isAppeal
          ? '请描述你认为哪些段落被误判、依据是什么'
          : '请描述你遇到的问题或建议，越具体越好'"
      />
      <view class="fb-count">{{ content.length }} / 2000</view>

      <input
        v-model="contact"
        class="fb-input"
        :maxlength="128"
        :cursor-spacing="80"
        :adjust-position="true"
        placeholder="联系方式（选填，方便我们回复）"
      />

      <button
        class="fb-submit" :class="{ disabled: !canSubmit }"
        :disabled="!canSubmit || submitting"
        :loading="submitting"
        @click="onSubmit"
      >{{ submitting ? '提交中…' : '提交' }}</button>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.fb-mask {
  position: fixed; left: 0; right: 0; top: 0; bottom: 0;
  background: rgba(0, 0, 0, 0.35);
  z-index: 999;
  display: flex; align-items: flex-end;
}
.fb-sheet {
  width: 100%;
  background: #FFFFFF;
  border-radius: 36rpx 36rpx 0 0;
  padding: 24rpx 32rpx 48rpx;
  box-shadow: 0 -4rpx 20rpx rgba(0, 0, 0, 0.08);
}
.fb-handle {
  width: 72rpx; height: 8rpx; border-radius: 4rpx;
  background: rgba(60,60,67,0.24); margin: 0 auto 24rpx;
}
.fb-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 24rpx;
}
.fb-title { font-size: 34rpx; font-weight: 600; color: #000; }
.fb-close { font-size: 36rpx; color: rgba(60,60,67,0.60); padding: 4rpx 12rpx; }

.fb-tabs {
  display: flex; padding: 6rpx;
  background: rgba(120,120,128,0.12);
  border-radius: 18rpx;
  margin-bottom: 24rpx;
}
.fb-tab {
  flex: 1; text-align: center; padding: 14rpx 0;
  font-size: 28rpx; color: #000;
  border-radius: 14rpx;
  transition: all 200ms cubic-bezier(0.32, 0.72, 0, 1);
  &.active {
    background: #FFFFFF; font-weight: 600;
    box-shadow: 0 3rpx 8rpx rgba(0,0,0,0.05);
  }
}
.fb-appeal-hint {
  padding: 20rpx 24rpx;
  background: rgba(0,122,255,0.08);
  border-radius: 18rpx;
  margin-bottom: 24rpx;
  font-size: 26rpx;
  color: rgba(60,60,67,0.85);
}
.fb-textarea {
  width: 100%; box-sizing: border-box;
  min-height: 240rpx;
  padding: 20rpx;
  background: rgba(120,120,128,0.08);
  border-radius: 18rpx;
  font-size: 30rpx;
  color: #000;
}
.fb-count {
  text-align: right; font-size: 22rpx;
  color: rgba(60,60,67,0.60);
  margin: 8rpx 6rpx 20rpx;
}
.fb-input {
  width: 100%; box-sizing: border-box;
  padding: 20rpx;
  background: rgba(120,120,128,0.08);
  border-radius: 18rpx;
  font-size: 28rpx;
  margin-bottom: 32rpx;
}
.fb-submit {
  width: 100%; height: 88rpx; line-height: 88rpx;
  background: #007AFF; color: #FFFFFF;
  font-size: 32rpx; font-weight: 600;
  border-radius: 20rpx;
  &.disabled { background: rgba(0,122,255,0.35); }
}

/* 段级申诉 */
.fb-paras { background: $bg-grouped-primary; border-radius: $radius-md; padding: $sp-3; margin-bottom: $sp-3; }
.fb-paras-title { display: block; font-size: $fs-footnote; font-weight: $fw-semibold; color: $label-primary; margin-bottom: $sp-2; }
.fb-paras-scroll { max-height: 280rpx; }
.fb-para { display: flex; align-items: center; gap: $sp-2; padding: $sp-2 0; }
.fb-para-box {
  flex: none; width: 36rpx; height: 36rpx; border-radius: $radius-xs;
  border: $stroke-thin solid $separator-opaque; background: $bg-primary;
  font-size: $fs-caption-1; color: #fff; display: flex; align-items: center; justify-content: center;
  &.on { background: $brand-primary; border-color: $brand-primary; }
}
.fb-para-tag { flex: none; font-size: $fs-caption-1; color: $danger-fg; font-weight: $fw-semibold; }
.fb-para-preview { flex: 1; font-size: $fs-caption-1; color: $label-secondary; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.fb-consent { display: flex; align-items: flex-start; gap: $sp-2; margin-top: $sp-2; padding-top: $sp-2; border-top: $stroke-hairline solid $separator; }
.fb-consent.off { opacity: 0.45; }
.fb-consent-text { font-size: $fs-caption-2; color: $label-secondary; line-height: $lh-normal; }
</style>
