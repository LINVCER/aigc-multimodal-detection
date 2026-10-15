<script setup>
import { ref, watch } from 'vue'
import { searchSchools, setMySchool } from '@/api/school'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue', 'saved'])

const q = ref('')
const list = ref([])
const loading = ref(false)
const picked = ref(null)
const degree = ref('master')
let timer = null

function onInput(e) {
  q.value = e.detail.value
  clearTimeout(timer)
  timer = setTimeout(doSearch, 300)
}
async function doSearch() {
  if (!q.value.trim()) { list.value = []; return }
  loading.value = true
  try { list.value = await searchSchools(q.value.trim()) } catch (e) {} finally { loading.value = false }
}
function pick(s) { picked.value = s }
function close() { emit('update:modelValue', false) }

async function save() {
  if (!picked.value) { uni.showToast({ title: '先选一所学校', icon: 'none' }); return }
  try {
    await setMySchool(picked.value.id, degree.value)
    uni.showToast({ title: '记好了，按你学校红线算', icon: 'none' })
    emit('saved'); close()
  } catch (e) {}
}
async function clearSchool() {
  try { await setMySchool(null, null); uni.showToast({ title: '已清除', icon: 'none' }); emit('saved'); close() } catch (e) {}
}

watch(() => props.modelValue, (v) => {
  if (v) { q.value = ''; list.value = []; picked.value = null; degree.value = 'master' }
})
</script>

<template>
  <view v-if="modelValue" class="mask" @click="close">
    <view class="sheet" @click.stop>
      <view class="handle" />
      <text class="title">你在哪所学校？</text>
      <view class="search">
        <input class="inp" :value="q" placeholder="搜学校名，北航 / 北京航空航天大学" placeholder-class="ph" @input="onInput" />
      </view>
      <scroll-view scroll-y class="list">
        <view v-for="s in list" :key="s.id" class="item" :class="{ on: picked && picked.id === s.id }" @click="pick(s)">
          <text class="nm">{{ s.name }}</text>
          <text class="pv">{{ s.province || '' }}</text>
        </view>
        <view v-if="!loading && q && !list.length" class="empty">没搜到，换个说法，或先用通用标准</view>
      </scroll-view>
      <view class="deg">
        <text class="lbl">你的学位</text>
        <view class="seg">
          <text v-for="d in [['bachelor','本科'],['master','硕士'],['phd','博士']]" :key="d[0]"
                class="seg-i" :class="{ on: degree === d[0] }" @click="degree = d[0]">{{ d[1] }}</text>
        </view>
      </view>
      <view class="foot">
        <text class="clear" @click="clearSchool">清除学校</text>
        <button class="save" @click="save">就选它</button>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
.mask { position: fixed; inset: 0; background: rgba(23,24,28,.4); z-index: 999; display: flex; align-items: flex-end; }
.sheet { width: 100%; background: $bg-primary; border-radius: 32rpx 32rpx 0 0; padding: 16rpx 32rpx calc(32rpx + env(safe-area-inset-bottom)); }
.handle { width: 72rpx; height: 8rpx; border-radius: 4rpx; background: $separator; margin: 8rpx auto 16rpx; }
.title { font-size: $fs-title-3; font-weight: $fw-semibold; color: $label-primary; }
.search { margin: 20rpx 0 12rpx; }
.inp { height: 80rpx; background: $bg-deep; border-radius: 16rpx; padding: 0 24rpx; font-size: $fs-body; color: $label-primary; }
.ph { color: $label-tertiary; }
.list { max-height: 460rpx; }
.item { display: flex; align-items: center; justify-content: space-between; padding: 24rpx; border-radius: 16rpx; }
.item.on { background: $brand-primary-wash; }
.item.on .nm { color: $brand-primary; font-weight: $fw-semibold; }
.nm { font-size: $fs-callout; color: $label-primary; }
.pv { font-size: $fs-footnote; color: $label-secondary; }
.empty { padding: 40rpx; text-align: center; color: $label-secondary; font-size: $fs-footnote; }
.deg { display: flex; align-items: center; gap: 20rpx; margin: 16rpx 0; }
.lbl { font-size: $fs-footnote; color: $label-secondary; }
.seg { display: flex; background: $bg-deep; border-radius: 16rpx; padding: 6rpx; }
.seg-i { padding: 12rpx 32rpx; border-radius: 12rpx; font-size: $fs-footnote; color: $label-secondary; }
.seg-i.on { background: $bg-primary; color: $label-primary; font-weight: $fw-semibold; box-shadow: $shadow-card; }
.foot { display: flex; align-items: center; justify-content: space-between; margin-top: 16rpx; }
.clear { font-size: $fs-footnote; color: $danger-fg; }
.save { height: 80rpx; line-height: 80rpx; padding: 0 48rpx; background: $brand-primary; color: #fff; font-size: $fs-headline; font-weight: $fw-semibold; border-radius: 24rpx; &::after { border: none; } }
</style>
