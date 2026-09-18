# COMPETITIVE_FEATURE_GAP · 对标 AIGC 检测头部平台的差距与补齐清单

> 调研范围：知网 · 维普 · 万方（国内三巨头）+ GPTZero · Turnitin（国际主流）
> 目标：识别当前平台的功能与样式空缺，按学术课题场景排优先级
> 报告日期：2026-09-18

---

## 0. 对标表（一屏）

| 能力 | 知网 | 维普 | 万方 | GPTZero | Turnitin | **我们** |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| 文档上传（PDF/DOC/DOCX/TXT） | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 文本粘贴（无文件即测） | ✅ | ✅ | ⚪ | ✅ | ✅ | ❌ |
| 批量上传 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| 段落级 / 句子级高亮 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 溯源（哪家 LLM） | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ✅ |
| 章节视图（摘要/引言/…） | ✅ | ✅ | ✅ | ⚪ | ✅ | ❌ |
| 参考文献 / 图表 / 公式过滤 | ✅ | ✅ | ✅ | ⚪ | ✅ | ❌ |
| 降 AIGC 改写建议 | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ✅ |
| 原文↔改写 diff | ⚪ | ⚪ | ⚪ | ⚪ | ⚪ | ✅ |
| PDF 报告导出 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| AI-paraphrased 子分数 | ⚪ | ⚪ | ⚪ | ⚪ | ✅（2026 新增） | ❌ |
| 修订版本对比 | ⚪ | ⚪ | ⚪ | ✅（Writing Process） | ⚪ | ❌ |
| 教师端 override | ⚪ | ⚪ | ⚪ | ⚪ | ✅ | ❌ |
| 组织/班级管理 | ⚪ | ⚪ | ⚪ | ✅ | ✅ | ❌（明确不做） |
| LMS 集成（Canvas/GC） | ⚪ | ⚪ | ⚪ | ✅ | ✅ | ❌（明确不做） |
| 付费 / 额度 / 发票 | ✅ | ✅ | ✅ | ✅ | ✅ | ❌（课题不做） |
| 私有化 / 等保 | ✅ | ✅ | ✅ | ⚪ | ✅ | ❌（课题不做） |

✅ = 有 · ⚪ = 无或不显著 · ❌ = 我们目前缺

**我们已有的差异化**：溯源（哪家 LLM）+ 降 AIGC 一体化 + 三档色高亮 —— 这三项**全场竞品都没同时具备**（TEAM_ROLES §1.4 的"5 张牌"里两张已落地）。

---

## 1. P0 · 强推补齐（每家都有，做完就是竞品级）

### 1.1 报告 PDF 导出 · 🔴 极刚需

**背景**：学生要交给学校 / 老师要归档 / 答辩要证据。竞品全支持，我们完全没做。

**建议做法**：
- **前端触发** `GET /api/v1/report/tasks/{id}` → 返回 `pdfUrl` → 浏览器 `<a download>` / 移动端 `uni.downloadFile`
- **后端** Java 用 iText 8 或 flying-saucer + Thymeleaf 模板：**封面页**（学校/学号/姓名/论文题目/学位类型/AI 率/达标状态/检测日期/溯源码）+ **正文分析页**（段落表 + 句子级高亮 + 溯源分布）
- **模板 3 种**：简洁版（1 页）· 详细版（完整段落列表）· 教师版（含 override 记录）—— 对齐知网的"简洁 vs 全文"

**工作量**：Java 侧 3-5 天（含模板设计）+ 前端下载按钮 1h

### 1.2 参考文献 / 图表 / 公式过滤 · 🔴 学术刚需

**背景**：论文里"参考文献 [1] 张三. 深度学习综述..."或"图 3-1 网络架构"被判 AI **冤枉 + 数据失真**。知网明确"自动识别过滤"。

**建议做法**：
- Java `splitParagraphs()` 之后加 `filterNonBody(paragraphs)`：
  - 参考文献段：段首匹配 `^\[\d+\]|^\d+\.\s+\S+|^参考文献$|^References$` 之后的所有段
  - 章节标题：段长 < 20 字 + 匹配 `^第.章|^\d+\.\d+|^Chapter|^Abstract|^摘要`
  - 图表 caption：`^图 ?\d|^表 ?\d|^Figure \d|^Table \d`
  - 公式段：段内 `$` / `\begin{equation}` 高密度
- 过滤掉的段 **保留在报告里但标注"不参与 AI 率计算"** —— 学生能看到系统识别对不对，透明

**工作量**：Java 侧 1-2 天

### 1.3 章节视图 · 🟡 教育强推

**背景**：论文有标准结构（摘要 / 引言 / 相关工作 / 方法 / 实验 / 结论 / 参考文献）。维普明确按章节加权（结论摘要权重高）。当前报告是段落顺序展开，看不出章节归属。

**建议做法**：
- Java 段落切分同时识别章节标题（正则 + 关键词）→ 每段标 `sectionName`
- 前端报告详情**新增章节维度视图**：Tab 切"段落视图 / 章节视图"
- 章节视图：每章一张卡（章节名 + 该章 AI 率 + 段数）→ 点开看该章段落
- 高亮"高风险章节"（结论/摘要 AI 率高，风险最大）

**工作量**：Java 1-2 天 + 前端 2-3 天

### 1.4 文本粘贴模式 · 🟡 移动端刚需

**背景**：GPTZero 有 3 模式（粘贴 / 单文件 / 批量），我们只有单文件。手机上写作时想快查一段没办法。

**建议做法**：
- 上传页加 **Tab 切换**："文件上传 / 文本粘贴"
- 粘贴模式：`<textarea>` 或 uni 输入框，字数上限 5000 字（避免滥用）
- 提交走 §8.2 已有的 `/api/v1/detect/paragraph` 直调，不生成 task
- 结果直接内联展示（不跳详情页）

**工作量**：前端 3 端各 2-4h

### 1.5 批量上传 · 🟢 教师场景加分

**背景**：老师批全班 30 篇论文，一个个传不现实。GPTZero + Turnitin 都有。

**建议做法**：
- 上传页加"批量"Tab → 一次选 ≤ 20 个文件
- 后端循环 `/detect/submit` 或新增 `/detect/submit/batch`
- 任务列表加"批次筛选"

**工作量**：前端 1 天 + 后端 4h（课题阶段可延后）

---

## 2. P1 · 增强能力（有则更好）

### 2.1 AI-paraphrased 子分数 · 🎯 直击对抗改写

**Turnitin 2026 新增能力**：独立标出"AI 生成 + humanizer 洗过"的段落。正好对应 `MODEL_RESEARCH_TEXT.md §4` 里的 DAMAGE / DIPPER 对抗防御 —— 学术上是我们已有的调研方向。

**建议**：Phase 2 上线主分类器时，独立训一个"洗稿检测子模型"，报告加 `paraphrasedProb` 字段。

### 2.2 句子级点击展开置信度详情

**GPTZero**：句子色码之外，点击任意句子看 "confidence 0.87 · 分支得分 statistical: 0.65 · roberta: 0.91 · logprob: 0.83"

**建议**：报告详情段落卡里每个句子加点击态，弹 `<popover>` 或行内展开。当前后端 stub 已返回 `branch_scores`（`deploy/inference-python/main.py` 里 statistical/deberta/roberta 三分支），前端展示即可。

**工作量**：前端 3-5h

### 2.3 Dashboard 数据统计

**背景**：首页只是任务列表。竞品的教育版 Dashboard 有：本月检测量 / 平均 AI 率 / 分布饼图 / 达标率趋势线。

**建议**：Dashboard 顶部加 4 个数字卡（今日/本月/累计/平均 AI 率）+ 一个折线图（最近 30 天 AI 率趋势）。

**工作量**：前端 1 天 + Java 加统计接口 4h

### 2.4 改进建议 / 教学提示

**知网**：报告有"综合评价 + 改进建议"文本段。

**建议**：报告最后加"改进建议"卡片，规则驱动：
- 若整体 AI 率 > 阈值：建议"用自己的话重写高亮段落"
- 若单章 AI 率 > 阈值 1.5×：建议"重点修改 {章节名} 章节"
- 若某个来源占比 > 40%：建议"避免大段复制 {来源名} 输出"

**工作量**：前端半天（纯规则模板，无需后端）

### 2.5 修订版本对比

**GPTZero Writing Process**：同一论文修改后重新检测，看 AI 率下降曲线 + 每次修订的段落对比。

**建议**：任务表加 `parentTaskId` 字段。UI 上"重新提交修订版"→ 详情页有"版本对比"tab。

**工作量**：Java 1 天 + 前端 1-2 天

---

## 3. P2 · 教育机构级（课题阶段建议不做，但可留 hook）

- 组织 / 班级 / 学生分组管理
- 教师端 override / 人工判定
- LMS 集成（Canvas / Google Classroom）
- 邀请码 / 团队协作

对齐 [TEAM_ROLES.md §4](TEAM_ROLES.md) 的"明确不做"负向清单。**若干年后想商业化再补**。

---

## 4. 样式层 gap（视觉与交互）

| 项 | 现状 | 竞品做法 | 建议 |
|---|---|---|---|
| **原文预览** | 只有段落文本重排展示 | 维普/Turnitin：**左侧 PDF 原文预览 + 右侧标注面板**（左右分栏） | web 端加左右分栏，mobile 端不适用 |
| **AI 率环形进度** | 静态大数字 | 竞品：环形动画 + 中央数字 | 加 SVG circular progress，冲击力更强 |
| **风险等级色阶** | 三档（绿/橙/红） | 知网四档（0.5-0.7 轻度 · 0.7-0.9 中度 · 0.9-1 高度） | 可选升级到四档 |
| **报告封面 UI** | 无 | 竞品 PDF 首页专业封面 | 配合 1.1 PDF 导出一起做 |
| **句子级可交互** | 只有底色 | GPTZero 每句可点看详情 | 配合 2.2 一起做 |
| **章节导航侧栏** | 无 | Turnitin/维普：详情页左侧目录树 | 配合 1.3 章节视图一起做（PC 端）|

---

## 5. 建议实施波次

### Wave 1（1 周内完成，做完就是竞品级）
- [ ] **1.1 PDF 报告导出**（Java 端最重）
- [ ] **1.2 参考文献 / 图表 / 公式过滤**（Java Tika 后加过滤器）
- [ ] **1.4 文本粘贴模式**（三端前端各加 tab）
- [ ] **2.4 改进建议卡片**（前端规则模板，纯 UI）

**验收**：学生提交一篇真实论文，导出的 PDF 直接能交给学校 + 参考文献不被冤枉打分。

### Wave 2（半个月）
- [ ] **1.3 章节视图**
- [ ] **1.5 批量上传**（教师场景）
- [ ] **2.3 Dashboard 数据统计**（首页信息密度）
- [ ] **样式：AI 率环形进度 · 报告封面 UI**

### Wave 3（Phase 2 结合模型能力）
- [ ] **2.1 AI-paraphrased 子分数**（等 DAMAGE 训练完）
- [ ] **2.2 句子级点击详情**
- [ ] **2.5 修订版本对比**
- [ ] **样式：PC 端左右分栏原文预览**

---

## 6. 需要你圈选的两个决策

**A. 从哪波开始 / 还是全 Wave 1 一次做完？**
- Wave 1 全做 → 我按 4 项顺序落地，全套约 3-5 天（当前 Java 侧改动最大：PDF + 过滤器）
- 只挑 1-2 项 → 你告诉我哪几项

**B. 样式层的四档色 / 环形进度 / 左右分栏 · 现在做还是等 Wave 2？**
- 建议随对应功能一起做（避免多次改动同一文件）

---

## 7. Sources（本次调研）

**知网**
- [知网 AIGC 检测完全指南 2026 版](https://www.linggantext.com/public/blog/cnki-aigc-detection-guide-2026/)
- [各大 AIGC 检测系统报告格式与内容特点详解（CSDN）](https://blog.csdn.net/2509_91422757/article/details/148057841)

**维普**
- [维普 AIGC 检测实战攻略 2026 版](https://www.linggantext.com/public/blog/weipu-aigc-detection-guide-2026/)
- [维普论文检测报告样本](https://www.cnweipu.com/demo/)

**万方**
- [维普·知网·万方·大雅 AIGC 检测 · PaperisOk](https://paperisok.com/aigc/)

**GPTZero**
- [GPTZero Reviews 2026 · G2](https://www.g2.com/products/gptzero/reviews)
- [GPTZero Review 2026 · Cybernews](https://cybernews.com/ai-tools/gptzero-review/)
- [Announcing GPTZero Docs](https://gptzero.me/news/announcing-gptzero-docs-the-future-of-transparent-writing/)

**Turnitin**
- [AI writing detection model · Turnitin Guides](https://guides.turnitin.com/hc/en-us/articles/28294949544717-AI-writing-detection-model)
- [Using the AI Writing Report · Turnitin Guides](https://guides.turnitin.com/hc/en-us/articles/22774058814093-Using-the-AI-Writing-Report)
- [Turnitin AI Detector Roadmap: Features Coming in 2026](https://turnitin.app/blog/Turnitin-AI-Detector-Roadmap-Features-Coming-in-2026.html)
