<script setup>
function goBack() {
  const pages = getCurrentPages()
  if (pages.length > 1) uni.navigateBack()
  else uni.switchTab({ url: '/pages/profile/profile' })
}
</script>

<template>
  <view class="page">
    <view class="back-bar" hover-class="back-bar-hover" @click="goBack">
      <text class="back-arrow">‹</text>
      <text class="back-text">我的</text>
    </view>

    <scroll-view class="content" scroll-y>
      <text class="title">隐私政策</text>
      <text class="updated">更新日期：2026 年 10 月 · 生效日期：即日</text>

      <view class="section">
        <text class="h2">一、我们收集什么</text>
        <text class="p">1. 账号信息：登录用的学号 / 工号及身份凭证，用于身份识别与登录鉴权。</text>
        <text class="p">2. 检测内容：你提交检测的论文原文、段落切分结果及 AI 率判定结果，用于生成检测报告。</text>
        <text class="p">3. 助手对话：你与「小白」检测助手的对话内容，用于回答你的问题。</text>
      </view>

      <view class="section">
        <text class="h2">二、我们怎么用</text>
        <text class="p">1. 检测服务：对你提交的论文做 AI 生成内容判定，产出段落级 / 句子级 AI 率、疑似来源（哪家大模型）与解释。</text>
        <text class="p">2. 服务改进：助手对话可能被人工抽样审阅以改进回答质量；审阅时你的身份信息（学号 / 工号）会被脱敏处理，只保留问答内容本身。</text>
        <text class="p">3. 我们不会将你的论文原文或对话内容用于广告投放，也不向第三方出售。</text>
      </view>

      <view class="section">
        <text class="h2">三、存储与保留</text>
        <text class="p">1. 论文原文加密存储，<text class="strong">30 天后自动删除</text>。</text>
        <text class="p">2. 检测报告保留 <text class="strong">3 年</text>，便于你随时回看与申诉举证。</text>
        <text class="p">3. 助手对话记录保留 <text class="strong">7 天</text>，到期自动清理。</text>
        <text class="p">4. 数据传输与存储均采用加密保护。</text>
      </view>

      <view class="section">
        <text class="h2">四、助手「小白」的边界</text>
        <text class="p">小白是检测与解释助手：帮你理解报告、解释「为什么像 AI」、给出合规的原创修改方向，并协助整理申诉材料。</text>
        <text class="p">小白<text class="strong">不代写、不洗稿、不绕过检测</text>——涉及代写、改写原文或编造申诉理由的请求，它会拒绝回答。</text>
      </view>

      <view class="section">
        <text class="h2">五、你的权利</text>
        <text class="p">1. 查看与导出：你可随时查看自己的检测报告。</text>
        <text class="p">2. 申诉：对判定结果有异议，可通过「结果申诉」提交复核，平台人工处理。</text>
        <text class="p">3. 删除：你可要求删除自己的账号与关联数据（法律要求保留的除外）。</text>
      </view>

      <view class="section">
        <text class="h2">六、联系我们</text>
        <text class="p">如对本政策或你的个人信息有任何疑问，可通过「我的 → 联系客服」或「意见反馈」与我们联系。</text>
      </view>
    </scroll-view>
  </view>
</template>

<style lang="scss" scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: $bg-grouped-primary;
}
.back-bar {
  flex: none;
  height: 88rpx;
  padding: 0 $sp-4;
  display: flex;
  align-items: center;
  gap: $sp-2;
  background: $bg-primary;
  border-bottom: $stroke-hairline solid $separator;
  &--hover { opacity: 0.7; }
}
.back-arrow { font-size: $fs-title-1; color: $brand-primary; line-height: 1; }
.back-text { font-size: $fs-body; color: $label-primary; }

.content {
  flex: 1;
  min-height: 0;
  padding: $sp-5 $sp-4 $sp-8;
}
.title { display: block; font-size: $fs-title-2; font-weight: $fw-bold; color: $label-primary; }
.updated { display: block; font-size: $fs-caption-1; color: $label-tertiary; margin-top: $sp-1; }

.section { margin-top: $sp-5; }
.h2 {
  display: block;
  font-size: $fs-headline;
  font-weight: $fw-semibold;
  color: $label-primary;
  margin-bottom: $sp-2;
}
.p {
  display: block;
  font-size: $fs-subhead;
  color: $label-secondary;
  line-height: $lh-normal;
  margin-bottom: $sp-2;
}
.strong { color: $label-primary; font-weight: $fw-semibold; }
</style>
