# 文献 AI 味预警：把检测从「写完查」前移到「读的时候筛」

> 2026-10 · 状态：方案 + 可行性调研，待拍板两项（§9）后开工。
> 关联：`202610-school-redline-plan.md`（同为留存向功能）、`202609-text-detector-training-pipeline.md`、`ml/datasets/text/README.md`「真实论文基线」、`202610-marketing-plan.md` 方向 B。

## 0. 问题

学生查资料读到的综述、公众号解读、知识星球笔记、部分低质量期刊论文，本身就是大模型写的。学生看了、改写了、引进自己的段落，AI 味跟着进了论文，终稿检测时已分不清是自己写得像还是来源就像。预警功能让学生在**引用之前**知道这份资料的文风风险。

它同时解决留存问题：论文检测每篇只用两三次，查资料在写论文的两个月里每天发生。

## 1. 可行性调研（2026-10-15，基于 master 代码）

| 项 | 现状 | 结论 |
|---|---|---|
| 单段即时检测 | `POST /api/v1/detect/paragraph` → `HttpInferenceClient.detectParagraph(text, returnSentences)` → 推理 `/api/v1/detect/paragraph`，返回 `ai_prob / calibrated_prob / risk_level / sentences` | 可直接复用，但只接一段文本，无切段与聚合 |
| 整篇链路 | `DetectTaskServiceImpl.submit`：Tika 抽取 → `TextProcessor.splitParagraphs` → `filterNonBody` → 逐段推理 → 聚合 AI 率 | 切段与排除规则可复用；聚合口径要为预警单独写 |
| HTML 正文抽取 | Tika 已在 `TextProcessor`，可解析 HTML；无公众号专用清洗 | 需加运营尾巴剥离规则 |
| 溯源 | `sourceLabel` 目前按 `calibratedProb` 阈值映射（≥0.7 qwen / ≥0.4 gpt），非模型输出 | 预警结果**暂不**展示溯源，待真溯源上线 |
| 真实论文假阳基线 | `ingest_thesis.py` + `eval.py` 已就位，等用户论文 | 预警阈值必须用它定，不能拍脑袋 |
| App 分享接收 | `manifest.json` 无 intent-filter / 无原生插件 | 需 Android `ACTION_SEND` 配置或原生插件，单独一期 |
| 文本存储 | 整篇检测存 `detect_task.paragraphs` 全文 | 预警模式不能复用该表存全文（见 §6） |

调研中发现一处与产品原则冲突的遗留：`POST /api/v1/humanize`（§4 降 AIGC，`DetectTaskServiceImpl.humanize` → 推理 `/api/v1/humanize` 返回 `rewritten_text`），web 与 App 的 api 层都有封装，页面上暂无入口。它就是「替用户改写」，与「不代写、不改写」的定位相悖，建议下线或至少从 api 层移除，见 §9 决策二。

## 2. 用户视角

### 2.1 入口

| 入口 | 说明 | 期 |
|---|---|---|
| 上传页粘贴模式 | 加一个开关「这是我要引用的资料」，开了走预警口径 | 一 |
| 小白对话 | 贴一段问「这段能引吗 / 这篇像 AI 写的吗」，意图识别后走同一接口 | 二 |
| 粘贴链接 | 公众号 / 博客 URL，服务端抓正文 | 二 |
| App 系统分享 | 微信长按文章「分享到知源」直接出结果 | 三 |

### 2.2 结果：三档风险 + 一句建议

| 档 | 判定 | 文案 | 动作 |
|---|---|---|---|
| 低 | 高概率段占比 < 15% 且无连续高概率段 | 「读起来像人写的，可以当资料用」 | — |
| 中 | 高概率段占比 15% ~ 40%，或有 2 段以上连续 | 「有几段 AI 味偏重，引用时用你自己的话重写，别照搬句式」 | 高亮这几段 |
| 高 | 高概率段占比 ≥ 40% | 「整篇像 AI 生成的，不建议作为参考文献，更别直接引用」 | 建议去找它引用的原始文献 |

每个结果固定带一句「这只说明文风，不代表内容对错」。

### 2.3 出版年份兜底

文本里解析到 DOI、期刊名加年份、或用户填了来源信息时，顺手判断发表年份：**2022 年及以前**直接标「发表于大模型普及前，AI 味是误报的可能性大」并把风险档降一级。这一条规则能挡掉大部分对经典文献的尴尬误报。

### 2.4 文案规则

沿用 style-prompt：口语、不用「您 / 请勿 / 提交」；结果页标题用「这篇资料怎么看」而不是「检测结果」；小白表情：低风险比心、中风险捂嘴、高风险摊手。

## 3. 口径：与论文检测的差别

| 维度 | 论文检测 | 文献预警 |
|---|---|---|
| 关心的问题 | 哪一段最像、先改哪段 | 整篇能不能当资料用 |
| 段级高概率线 | calibrated ≥ 0.4 中、≥ 0.7 高 | 初值 ≥ 0.55 中、≥ 0.8 高，**最终用真实论文基线定** |
| 聚合 | 加权 AI 率 vs 学校红线 | 高概率段占比 + 连续性（§2.2） |
| 单段触发 | 一段高就进「先改这几段」 | 一两段高不报，防止把正经文献全标黄 |
| 排除规则 | 参考文献 / 致谢 / 图表题 / 章节标题 | 同上 + 公众号运营尾巴（「点击关注」「往期推荐」「扫码」等）+ 转载声明 |
| 溯源 | 展示 | 暂不展示（§1） |
| 存储 | 全文入 `detect_task.paragraphs` | 不存全文（§6） |

阈值定法：真实论文基线出来后，取「已发表论文集」上整篇被判中 / 高风险的比例作为假阳率，目标 **FPR ≤ 5%**，反推段级线和占比线。基线没出来之前预警只在内测开关下可见。

## 4. 技术方案

### 4.1 接口

`POST /api/v1/detect/reference`

请求：`{ text?: string, url?: string, sourceHint?: { title?, year?, doi? } }`，text 与 url 二选一；text 上限 20000 字。

响应：

```json
{
  "riskLevel": "low | medium | high",
  "highRatio": 0.23,
  "paragraphCount": 18,
  "highParagraphs": [{ "idx": 3, "prob": 0.86, "text": "…" }],
  "publishedYear": 2019,
  "yearDowngraded": true,
  "advice": "有几段 AI 味偏重，引用时用你自己的话重写",
  "modelVersion": "v3"
}
```

### 4.2 服务端流程

1. url 分支：服务端抓取（白名单域名：mp.weixin.qq.com、zhihu、csdn、博客类；知网 / 万方 / 维普不抓，提示用户粘贴正文），Tika 抽 HTML 正文，再按 §3 剥离运营尾巴。
2. `TextProcessor.splitParagraphs` + `filterNonBody`（复用）。
3. 逐段调 `inferenceClient.detectParagraph(text, false)`，并发度与整篇检测一致。
4. 按 §2.2 聚合，§2.3 年份兜底。
5. 落 `detect_reference_log`（§6），返回结果。

限流：匿名每 IP 每日 5 次，登录用户每日 50 次，复用 `IpRateLimiter`。

### 4.3 前端

- web `Upload.vue` 粘贴模式加 `el-switch`「这是我要引用的资料」，结果区换成三档卡片 + 高亮段列表；App `pages/upload/upload.vue` 同步。
- 小白：`AssistantServiceImpl` 增工具 `check_reference`，参数 text / url，返回 §4.1 结构，由助手翻译成口语。
- 结果卡的分享只允许分享「我检查过这篇资料」这个动作，不带分数、不带来源标题。

### 4.4 App 系统分享（第三期）

Android 需要 `ACTION_SEND`（text/plain）intent-filter，uni-app 原生 manifest 不直接支持，两条路：HBuilderX 自定义基座加 `AndroidManifest.xml` 片段并用 `plus.runtime.arguments` 读取；或接原生插件。iOS 需 Share Extension，uni-app 侧成本更高，第三期只做 Android。

## 5. 数据与指标

- 日预警次数、预警用户中 7 日内做整篇检测的比例（前移是否带动主检测）。
- 三档分布；中 / 高风险里用户点「还是要引用」的比例（判断是否过严）。
- 来源域名分布与风险档交叉表，这份数据可做公众号内容（营销方向 B）。

## 6. 边界

- **结果只对本人可见**，不做任何公开榜单或来源排名；分享卡片不带分数与标题。
- **不替用户决定能不能引用**，文案永远是建议。
- **不存全文**：`detect_reference_log` 只记 user_id、source_domain、paragraph_count、high_ratio、risk_level、published_year、created_at，文本处理完即丢，高亮段只回传不落库。
- **不抓取知网 / 万方 / 维普**页面，避免版权与反爬。
- **与 humanize 划清界限**：预警页面不出现任何「改写 / 降 AI」入口。

## 7. 分期

| 期 | 内容 | 涉及 |
|---|---|---|
| 一 | `/detect/reference` 接口（text 分支）+ 聚合口径 + 上传页开关与三档结果 + 内测开关；真实论文基线出来后定阈值并放开 | ruoyi-detect、web、mobile-uniapp、ml/evaluation |
| 二 | url 分支与公众号清洗；小白 `check_reference` 工具；年份兜底；指标埋点 | ruoyi-detect、assistant |
| 三 | Android 系统分享接收；来源域名风险分布运营看板 | mobile-uniapp 原生、后台 |

第一期除阈值外几乎没有模型成本，推理与切段链路都是现成的。

## 8. 验收

1. 同一段文本，论文模式与预警模式返回不同风险判定，口径按 §3。
2. 已发表论文集（基线）整篇中 / 高风险比例 ≤ 5%。
3. 公众号样例文章运营尾巴不计入段数。
4. `detect_reference_log` 无正文字段；接口返回后库里查不到任何原文。
5. 文案无「您 / 请勿 / 提交」，无改写入口。

## 9. 待拍板

| 决策 | 选项 | 建议 |
|---|---|---|
| 一 · 阈值未定前要不要先上 | A 内测开关，基线出来再放开 / B 先用 0.55 / 0.8 直接上 | A，预警一上线就把正经文献标黄会砸可信度 |
| 二 · 遗留 `humanize` 接口 | A 下线接口并移除两端 api 封装 / B 保留接口不暴露入口 | A，与「不代写」定位冲突，留着是风险 |
