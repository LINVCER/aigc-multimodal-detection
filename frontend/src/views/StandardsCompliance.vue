<template>
  <div class="standards-page">
    <h1>国家标准合规</h1>
    <p style="color:#718096;margin-top:0">AIGC--多模态检测平台对标国家标准情况</p>

    <!-- 核心标准 -->
    <h2 style="margin-top:28px">核心对标标准</h2>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:16px">
      <div v-for="s in coreStandards" :key="s.id" class="standard-card" :class="'level-' + s.level">
        <div class="card-header">
          <el-tag :type="s.level === 'full' ? 'success' : 'warning'" size="small">{{ s.level === 'full' ? '完全符合' : '部分符合' }}</el-tag>
          <span class="card-id">{{ s.id }}</span>
        </div>
        <div class="card-title">{{ s.name }}</div>
        <div class="card-desc">{{ s.desc }}</div>
        <div class="card-detail">
          <div v-for="d in s.details" :key="d" class="detail-item">
            <span class="check">&#10003;</span> {{ d }}
          </div>
        </div>
      </div>
    </div>

    <!-- GB 45438 详情 -->
    <h2 style="margin-top:36px">GB 45438—2025 对标详情</h2>
    <el-card style="margin-top:16px">
      <el-table :data="gb45438Items" stripe border style="width:100%">
        <el-table-column prop="requirement" label="标准要求" min-width="200" />
        <el-table-column label="本项目实现" min-width="300">
          <template #default="{ row }">
            <div v-for="item in row.implementation" :key="item" style="margin-bottom:2px">
              <span style="color:#10b981;font-weight:600">&#10003;</span> {{ item }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="符合度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.compliance === 'full' ? 'success' : 'warning'" size="small">
              {{ row.compliance === 'full' ? '完全' : '部分' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 适用范围 -->
    <h2 style="margin-top:36px">适用法规</h2>
    <el-card style="margin-top:16px">
      <div v-for="r in regulations" :key="r.id" class="reg-item">
        <div style="display:flex;align-items:center;gap:8px">
          <span class="reg-badge">{{ r.dept }}</span>
          <span class="reg-name">{{ r.name }}</span>
          <el-tag size="small" type="info">{{ r.year }}</el-tag>
        </div>
        <div class="reg-desc">{{ r.desc }}</div>
        <div v-if="r.benefits?.length" class="reg-benefits">
          <span v-for="b in r.benefits" :key="b" class="benefit-tag">{{ b }}</span>
        </div>
      </div>
    </el-card>

    <!-- 底部说明 -->
    <div style="margin-top:36px;padding:20px;background:#f0f9ff;border-radius:12px;border-left:4px solid #409eff">
      <div style="font-weight:600;margin-bottom:8px;color:#1e40af">合规声明</div>
      <div style="font-size:14px;color:#4a5568;line-height:1.8">
        AIGC--多模态检测平台严格对标 GB 45438—2025《人工智能 生成内容标识方法》和
        TC260-003《生成式人工智能服务安全基本要求》设计实现。<br/>
        平台提供显式标识检测、隐式标识(元数据)验证、生成模型溯源和风险等级评定等核心功能，
        适用于教育、出版、传媒等领域的 AIGC 内容合规检测场景。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const coreStandards = [
  {
    id: "GB 45438—2025",
    name: "人工智能 生成内容标识方法",
    desc: "国家标准，规定AI生成内容的显式标识(水印/标记)和隐式标识(元数据)要求",
    level: "full",
    details: [
      "显式标识检测: 文本标记/图像水印/音频提示音自动识别",
      "隐式标识检测: XMP/IPTC/EXIF 元数据字段验证",
      "生成模型名称、生成时间、内容哈希、版权声明四要素检测",
      "合规等级评定: none/partial/full 三档",
    ],
  },
  {
    id: "TC260-003",
    name: "生成式人工智能服务安全基本要求",
    desc: "全国信息安全标准化技术委员会，生成式AI服务上线前的安全检测基准",
    level: "full",
    details: [
      "内容溯源可追溯，支持多模型置信度对比",
      "风险等级 low/medium/high 三档分级",
      "知网风格三色标注检测报告输出",
    ],
  },
  {
    id: "TC260-PG-20233A",
    name: "生成式人工智能服务内容标识要求",
    desc: "信安标委实践指南，细化生成内容的标识方法和格式",
    level: "full",
    details: [
      "C2PA 内容来源与真实性元数据检测",
      "隐式水印: 文本/图像/音频各模态全覆盖",
    ],
  },
  {
    id: "深度合成管理规定",
    name: "互联网信息服务深度合成管理规定",
    desc: "国家互联网信息办公室令，2023年1月10日施行",
    level: "full",
    details: [
      "文本/图像/音频三模态深度合成检测全覆盖",
      "检测报告可作为合规审计依据",
    ],
  },
]

const gb45438Items = [
  {
    requirement: "显式标识 — 文本",
    implementation: ["检测 @AI生成 等显式标记文字", "支持自定义标记模式匹配"],
    compliance: "full",
  },
  {
    requirement: "显式标识 — 图像",
    implementation: ["检测图像中的 AI 生成水印/标记", "支持 C2PA/Content Credentials 验证"],
    compliance: "full",
  },
  {
    requirement: "显式标识 — 音频",
    implementation: ["检测音频开头的 AI 合成提示音", "支持自定义提示音模式"],
    compliance: "partial",
  },
  {
    requirement: "隐式标识 — 元数据",
    implementation: ["XMP 命名空间: xmpMM:Generator / dc:creator", "IPTC 字段: CopyrightNotice / Creator", "EXIF 字段: Artist / Software / ImageDescription", "PNG tEXt/iTXt chunk 检测"],
    compliance: "full",
  },
  {
    requirement: "生成模型名称",
    implementation: ["model_attribution 多模型溯源", "RoBERTa/Wav2Vec2/ViT 置信度独立输出"],
    compliance: "full",
  },
  {
    requirement: "生成时间",
    implementation: ["解析元数据中的 CreateDate/DateTimeOriginal", "检测报告含 detection_time"],
    compliance: "full",
  },
  {
    requirement: "内容哈希",
    implementation: ["SHA-256 文件完整性验证", "元数据哈希与文件哈希交叉比对"],
    compliance: "full",
  },
  {
    requirement: "风险等级",
    implementation: ["低风险: AI率 < 15%", "中风险: AI率 15-30%", "高风险: AI率 > 30%"],
    compliance: "full",
  },
]

const regulations = [
  {
    id: "r1",
    dept: "网信办",
    name: "互联网信息服务深度合成管理规定",
    year: "2023",
    desc: "要求深度合成服务提供者对生成内容进行标识，平台需具备检测能力。本项目可直接用于教育/出版机构的合规检测工具。",
    benefits: ["三模态检测", "检测报告", "合规审计"],
  },
  {
    id: "r2",
    dept: "网信办",
    name: "生成式人工智能服务管理暂行办法",
    year: "2023",
    desc: "要求生成式AI服务遵守内容标识、安全评估等义务。本项目提供的内容溯源和风险分级功能满足合规要求。",
    benefits: ["内容溯源", "风险分级", "模型归因"],
  },
  {
    id: "r3",
    dept: "教育部",
    name: "学位论文作假行为处理办法（征求意见修订稿）",
    year: "2024",
    desc: "拟将 AIGC 检测纳入学位论文审核流程。本项目论文 AIGC 检测模块专为此场景设计，支持三色标注+取证分析报告。",
    benefits: ["论文专项", "三色标注", "取证分析"],
  },
]
</script>

<style scoped>
.standards-page { max-width: 900px; margin: 0 auto; }
.standard-card {
  padding: 20px; border-radius: 12px; border: 1px solid #e2e8f0;
  background: white; transition: box-shadow .2s;
}
.standard-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,.08); }
.standard-card.level-full { border-left: 4px solid #10b981; }
.standard-card.level-partial { border-left: 4px solid #f59e0b; }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.card-id { font-family: monospace; font-size: 13px; color: #718096; }
.card-title { font-size: 16px; font-weight: 700; color: #1a202c; margin-bottom: 6px; }
.card-desc { font-size: 13px; color: #718096; line-height: 1.6; margin-bottom: 12px; }
.card-detail { font-size: 13px; color: #4a5568; line-height: 1.8; }
.detail-item { margin-bottom: 2px; }
.check { color: #10b981; font-weight: 700; }
.reg-item { padding: 14px 0; border-bottom: 1px solid #f1f5f9; }
.reg-item:last-child { border-bottom: none; }
.reg-badge { display: inline-block; padding: 2px 8px; background: #eff6ff; color: #3b82f6; border-radius: 4px; font-size: 12px; font-weight: 600; }
.reg-name { font-weight: 600; font-size: 14px; }
.reg-desc { font-size: 13px; color: #718096; margin-top: 6px; line-height: 1.6; }
.reg-benefits { margin-top: 8px; display: flex; gap: 6px; }
.benefit-tag { padding: 2px 8px; background: #f0fdf4; color: #16a34a; border-radius: 4px; font-size: 12px; }
</style>
