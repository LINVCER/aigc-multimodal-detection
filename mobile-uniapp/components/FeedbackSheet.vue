<script setup>
import { computed, ref, watch } from 'vue'
import { submitFeedback } from '@/api/feedback'
import { useAuth } from '@/store/auth'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  taskId:  { type: Number, default: 0 },       // 传值 => 锁定 appeal 分类
  defaultCategory: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])
const auth = useAuth()

const category = ref(props.defaultCategory || (props.taskId ? 'appeal' : 'suggestion'))
const content  = ref('')
const contact  = ref('')
const submitting = ref(false)

const canSubmit = computed(() => content.value.trim().length > 0 && content.value.length <= 2000)
const isAppeal  = computed(() => category.value === 'appeal')

watch(() => props.modelValue, (v) => {
  if (v) {
    category.value = props.defaultCategory || (props.taskId ? 'appeal' : 'suggestion')
    content.value = ''
    contact.value = ''
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

      <textarea
        v-model="content"
        class="fb-textarea"
        :maxlength="2000"
        :placeholder="isAppeal
          ? '请描述你认为哪些段落被误判、依据是什么'
          : '请描述你遇到的问题或建议，越具体越好'"
      />
      <view class="fb-count">{{ content.length }} / 2000</view>

      <input
        v-model="contact"
        class="fb-input"
        :maxlength="128"
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
</style>
