<script setup>
/*
 * SparkLine 星点图标（App 端）· 对齐 docs/design/202610-web-visual-redesign-plan.md §4
 *   24×24 细线、圆头圆角、主笔画末端带四角星点；颜色跟随 color 属性（默认继承文字色）。
 *   实现：SVG 作 mask + 背景色上色，一个组件覆盖全部图标，不引图标库、不用 emoji。
 *   小程序端不支持 mask，退化为单色方块；主线是 App / H5，可接受。
 */
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 32 },   // rpx
  color: { type: String, default: 'currentColor' },
})

// 共用的星点签名（右上角 2px 四角星），拼在每个图标主笔画末端
const SPARK = "<path d='M19 2.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z' fill='%23000' stroke='none'/>"
const ICONS = {
  search: "<circle cx='10.5' cy='10.5' r='6'/><path d='M15 15l4.5 4.5'/>",
  'pen-line': "<path d='M4 20h16'/><path d='M14 4l4 4-9 9H5v-4z'/>",
  'file-text': "<path d='M7 3h7l5 5v13H7z'/><path d='M14 3v5h5'/><path d='M9.5 13h7M9.5 16.5h5'/>",
  flask: "<path d='M9.5 3h5'/><path d='M10 3v6l-5.5 9.5a1.5 1.5 0 0 0 1.3 2.3h12.4a1.5 1.5 0 0 0 1.3-2.3L14 9V3'/><path d='M7.5 15h9'/>",
  flag: "<path d='M6 21V4'/><path d='M6 4h11l-2.5 4 2.5 4H6'/>",
  history: "<path d='M4 12a8 8 0 1 0 2.5-5.8'/><path d='M4 4v4.5h4.5'/><path d='M12 8v4.5l3 1.8'/>",
  plus: "<path d='M12 5v14M5 12h14'/>",
  sparkle: "<path d='M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z'/>",
  chat: "<path d='M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-4 3.5V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'/>",
  chart: "<path d='M4 20h16'/><path d='M7 16v-5M12 16V7M17 16v-8'/>",
  book: "<path d='M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z'/><path d='M5 19.5A1.5 1.5 0 0 0 6.5 21H19'/>",
  ruler: "<path d='M3 17L17 3l4 4L7 21z'/><path d='M8 12l1.5 1.5M11 9l1.5 1.5M14 6l1.5 1.5'/>",
  graduation: "<path d='M3 9.5l9-4.5 9 4.5-9 4.5z'/><path d='M7 11.5v4.5c0 1.5 2.5 2.5 5 2.5s5-1 5-2.5v-4.5'/><path d='M21 9.5v5'/>",
  clipboard: "<path d='M9 4h6v3H9z'/><path d='M15 5h2.5a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1H9'/><path d='M9 12h6M9 16h4'/>",
  close: "<path d='M6 6l12 12M18 6L6 18'/>",
  check: "<path d='M5 12.5l4.5 4.5L19 7.5'/>",
  'thumb-up': "<path d='M7 11v9H4v-9z'/><path d='M7 11l4-7c1.5 0 2.5 1 2.5 2.5V10h4.5a2 2 0 0 1 2 2.3l-1 6A2 2 0 0 1 17 20H7'/>",
  'thumb-down': "<path d='M17 13V4h3v9z'/><path d='M17 13l-4 7c-1.5 0-2.5-1-2.5-2.5V14H6a2 2 0 0 1-2-2.3l1-6A2 2 0 0 1 7 4h10'/>",
  compass: "<circle cx='12' cy='12' r='8.5'/><path d='M15 9l-2 5-5 2 2-5z'/>",
  shield: "<path d='M12 3l7 3v6c0 4-3 7-7 9-4-2-7-5-7-9V6z'/><path d='M9 12l2 2 4-4'/>",
  tool: "<path d='M14.5 6.5a4 4 0 0 0 5 5L13 18l-3-3 6.5-6.5a4 4 0 0 1 0-2z'/><path d='M10 15l-5 5'/>",
  'chevron-right': "<path d='M9 6l6 6-6 6'/>",
  'chevron-down': "<path d='M6 9l6 6 6-6'/>",
  'arrow-left': "<path d='M19 12H5M11 6l-6 6 6 6'/>",
  send: "<path d='M4 12L20 4l-4 16-4-7z'/><path d='M12 13l8-9'/>",
  more: "<circle cx='6' cy='12' r='1.2'/><circle cx='12' cy='12' r='1.2'/><circle cx='18' cy='12' r='1.2'/>",
  rotate: "<path d='M20 12a8 8 0 1 1-2.3-5.7'/><path d='M20 4v4.5h-4.5'/>",
  download: "<path d='M12 4v11M7 10l5 5 5-5'/><path d='M4 19h16'/>",
  link: "<path d='M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1.2 1.2'/><path d='M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1.2-1.2'/>",
  'upload-cloud': "<path d='M7 18a4.5 4.5 0 0 1-.5-9A6 6 0 0 1 18 8.5 4 4 0 0 1 18 16.5'/><path d='M12 20v-8M8.5 15.5L12 12l3.5 3.5'/>",
  alert: "<circle cx='12' cy='12' r='9'/><path d='M12 8v5M12 16h.01'/>",
  'xiaobai-spark': "<circle cx='12' cy='13' r='7'/><path d='M12 6V3M12 3l1.5-1.5'/><circle cx='9.5' cy='12.5' r='.8' fill='%23000'/><circle cx='14.5' cy='12.5' r='.8' fill='%23000'/><path d='M10 15.5c1 .8 3 .8 4 0'/>",
}

const mask = computed(() => {
  const body = ICONS[props.name] || ICONS.alert
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round'>${body}${SPARK}</svg>`
  return `url("data:image/svg+xml;utf8,${svg}")`
})
const px = computed(() => (typeof props.size === 'number' ? `${props.size}rpx` : props.size))
</script>

<template>
  <view
    class="zy-icon"
    :style="{ width: px, height: px, backgroundColor: color, '-webkit-mask-image': mask, 'mask-image': mask }"
  />
</template>

<style scoped>
.zy-icon {
  display: inline-block;
  flex: none;
  vertical-align: middle;
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center;
  mask-position: center;
  -webkit-mask-size: contain;
  mask-size: contain;
}
</style>
