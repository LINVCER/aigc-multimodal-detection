# 知源 Web 端整体视觉重设计方案 ——「知源小白」AI 助手风

> 2026-10 · 适用于 `web/`（Vue 3 + Element Plus）。风格参考现代 AI 智能助手产品（ChatGPT / Kimi / 豆包）：极简留白、圆融友好、星点渐变、对话优先。方案产物：设计令牌替换表、独有图标体系（SparkLine）、首页大图设计、逐页逐按钮规范、实施拆解。

---

## 1. 现状诊断

| 问题 | 现状 | 位置 |
|---|---|---|
| 风格同质化 | 全站套用 Apple iOS 体系（system-blue `#007AFF`、pill 按钮、F2F2F7 冷灰底），和任何一款蓝色 SaaS 无差别，没有品牌记忆点 | [tokens.scss](file:///d:/AAA/image_nious/web/src/styles/tokens.scss) |
| 图标缺失 | 全站**零图标库**，40+ 处用 emoji 当图标（💬🚩🔗⬇🕘✚✕📊👤📄🤖📈…），各平台渲染不一致、风格涣散 | 全部页面 |
| 按钮不成体系 | 134 处 `el-button`，pill / 圆角 / link / plain 混用，图标前缀有的用 emoji 有的没有 | 全部页面 |
| 首页无视觉锚点 | Hero 只有文字 + 一个模拟报告卡，没有大图，第一屏缺乏情绪和信任感；品牌已有「小白」IP 却没在 web 端露出 | [Landing.vue](file:///d:/AAA/image_nious/web/src/views/Landing.vue) |

## 2. 设计定位：「知源小白」AI 助手风 · 大学生的论文搭子

参考对象：现代 AI 智能助手产品（ChatGPT / Kimi / 豆包）的共同语言——**大留白、暖白底、圆角几何、柔和环境光、星点/渐变的 AI 语义、对话优先**；情绪参照豆包、小红书式的**年轻、元气、有梗**，目标用户是在校大学生，界面要像一个靠谱又可爱的「论文搭子」，而不是一个冰冷的检测工具。同时把品牌自有的「小白」IP 用起来，避免做成又一个蓝色渐变模板：

- **智能青（teal）为主色**——直接取自小白形象（青绿触角、青绿眼睛、青绿气泡），这是产品已经长期露出的品牌资产，比通用「AI 蓝渐变」更独有；
- **元气橙做情绪点缀**（贴纸、徽章、小白腮红同源的暖色），只在「鼓励 / 奖励 / 彩蛋」时刻出现，不进操作色；
- **青→蓝渐变**只出现在品牌时刻（hero、大标题徽标、小白语义），日常界面保持单色克制；
- **星点（sparkle ✦）**是 AI 语义装饰：生成中、助手回答、溯源结果等「AI 在思考」的时刻；
- **圆融几何 + 胖按钮**：按钮回归大圆角、高度加胖（更好点），关键 CTA 用 pill（Kimi、豆包的输入区语言），卡片 16px，无尖角；
- **暖白底** `#FAF9F6` + 白卡片 + 发丝边框——比冷灰白更有「温度」，环境光是柔和的青色调阴影；
- **对话优先 + 口语文案**：小白入口全站常驻，报告页第一动作永远是「问小白」；文案全部说人话——「还没有检测记录，交一篇试试？」「小白正在逐段读你的论文…」「这段太『AI 味』了，加一句你自己的实验细节」，禁止「尊敬的用户 / 请勿 / 您」；
- **小白表情包化**：小白按场景出表情——加载中打哈欠、检测完成比心、超线捂嘴、申诉握拳，用在空态、加载态、结果 hero 与 toast，让每个状态都有情绪陪伴；
- 字体不引入衬线，保持现代无衬线，靠字重和字号做层级。

一句话：**打开任何一个页面，都像在和那个聪明又暖的白团子说话——它在陪你过「论文这一关」。**

## 3. 设计令牌替换（tokens.scss）

### 3.1 色板

| Token | 旧值（Apple） | 新值（AI 助手风） | 用途 |
|---|---|---|---|
| `--ai-700` | `#007AFF` (system-blue) | `#0F766E` | **主色**：主按钮、链接、焦点环（白字对比 4.8:1，AA） |
| `--ai-500` | — | `#14B8A6` | 小白形象同源青：渐变端点、选中态、装饰 |
| `--ai-100` | — | `rgba(20,184,166,0.10)` | tinted 底、选中态、hover |
| `--grad-ai` | — | `linear-gradient(135deg,#14B8A6,#3B82F6)` | 品牌时刻：hero 徽标、小白语义高亮 |
| `--accent-orange` | — | `#FF8A3D` | 元气橙：鼓励徽章、彩蛋、小白贴纸点缀，不进操作色 |
| `--accent-pink` | — | `#FF9EB5` | 小白腮红同源：点赞、感谢等暖心时刻点缀 |
| `--success` | `#34C759` | `#16A34A` | 达标、成功 |
| `--warning` | `#FF9500` | `#F59E0B` | 黄区预警 |
| `--danger` | `#FF3B30` | `#E5484D` | 超线、申诉、危险操作 |
| `--bg` | `#F2F2F7` | `#FAF9F6` | 页面底（**暖白**，豆包式温度感，替代冷灰白） |
| `--bg-deep` | — | `#F1EFEA` | 分区块底、输入底、segmented 底（同步暖化） |
| `--card` | `#FFFFFF` | `#FFFFFF` | 卡片 |
| `--label` | `#000000` | `#17181C` | 正文 |
| `--label-secondary` | `rgba(60,60,67,.60)` | `rgba(23,24,28,.62)` | 次级文字 |
| `--label-tertiary` | `rgba(60,60,67,.30)` | `rgba(23,24,28,.38)` | 辅助文字 |
| `--separator` | `rgba(60,60,67,.29)` | `rgba(23,24,28,.10)` | 分隔线（发丝） |

- Element Plus 映射：`--el-color-primary: var(--ai-700)`、`success / warning / danger` 同步换 §3.1 语义色；
- 对比度：`#0F766E` 于白 ≈ 5.9:1（正文 AA）；`#E5484D` 于白 ≈ 4.6:1（AA）；`#14B8A6` 只做装饰与底色，不单独承担正文文字；
- 语义沿用现有「红黄绿」报告三色映射：超线/可疑 → danger、黄区 → warning、达标 → success。

### 3.2 字体

| 层级 | 旧 | 新 |
|---|---|---|
| 展示标题（h1 / hero / 大数字） | 系统无衬线 700 | 不变，`letter-spacing: -0.8px`，大数字 `tabular-nums` |
| 正文 / UI | 系统无衬线 | 不变（`-apple-system, PingFang SC…`） |
| 等宽数字 | — | `ui-monospace` 用于 AI 率、z 值、编号 |

不引入新字体文件（零网络成本、零 CLS），层级靠字重 500/600/700 + 尺寸阶梯（沿用现有 Apple ramp）。

### 3.3 圆角与尺寸

| Token | 旧 | 新 | 理由 |
|---|---|---|---|
| `--radius-btn` | 10px | **12px** | 常规操作按钮，更胖更圆更好点 |
| `--radius-cta` | — | **pill（9999px）** | 关键 CTA / 小白对话入口（豆包、Kimi 的对话按钮语言） |
| `--radius-card` | 14px | **16px** | AI 助手产品的标准卡片圆角 |
| `--radius-sheet` | 20px | **20px** | 弹层 |
| 按钮高度 | default 32 / large 40 | **default 36 / large 46 / small 28** | 胖按钮：更大的点击面积与「软弹」观感，学生端不追求密度效率 |
| pill 收敛规则 | 全站大量 round | **pill 只用于**：hero 双 CTA、发送按钮、小白相关按钮、灵感 chips、弹层确认 | pill = 「对话感」，用在对话与转化上，不滥用于表格操作 |

### 3.4 阴影与边框（环境光语言）

- 卡片：`border: 1px solid rgba(23,24,28,0.08); box-shadow: 0 2px 8px rgba(23,24,28,0.05);`
- 重点卡片（hero 报告卡、结果 hero）：`box-shadow: 0 4px 12px rgba(23,24,28,0.06), 0 16px 40px rgba(15,118,110,0.10);`（环境光带一点青）
- 顶栏保留现有 backdrop blur 玻璃效果（已是 AI 助手产品通用做法）；
- 「AI 在思考」的元素允许极轻外发光：`box-shadow: 0 0 0 4px var(--ai-100)`。

### 3.5 动效

- 保留 `--ease-standard` 做通用过渡；**主按钮与小白元素用弹簧曲线** `--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)`——按压回弹、小白冒泡入场带 1-2px 微弹跳，年轻但不闹腾；
- **sparkle 动效**：小白回答完成的星点 250ms 缩放淡入（`@media (prefers-reduced-motion)` 下关闭）；
- **小白呼吸**：常驻小白图标 / FAB 用 3s 循环 ±2% 缩放呼吸，页面空闲时才感知得到，交互中不打扰；
- 按钮 hover 统一背景 tint 过渡 160ms；主按钮按压保留 `scale(0.98)`（回弹用 spring），link/text 去掉。

## 4. 独有图标体系：SparkLine 星点图标

### 4.1 视觉规格（签名风格）

- 画布 24×24，`stroke-width: 1.75`，`stroke-linecap/join: round`，默认无填充，颜色走 `currentColor`——与 AI 助手产品的细线图标一致；
- **签名细节——星点收尾**：每个图标主笔画的末端带一个 2px 四角星点（sparkle），呼应「AI 在思考」的品牌语义，是全站可辨识的家族特征；
- 圆优先：容器类元素（文档、盾牌、气泡）用大圆角（r≥5），无尖角；
- 选中态允许 `fill: currentColor` + 0.12 透明度自填充；
- 小白专属图标 `xiaobai-spark` 例外使用双色（青主体 + 星点渐变蓝）。

### 4.2 落地方式

```
web/src/components/icons/
  ZyIcon.vue            # <ZyIcon name="flag" :size="16"/>，内部 <svg><use/></svg> sprite
  svg/                  # 每个 icon 一个 svg 文件，vite-plugin-svg-icons 打 sprite
```

替换规则：全局 grep emoji 一处不留（验收项）；不引入 Element Plus 图标包，保持独立。

### 4.3 图标清单（emoji → SparkLine 映射，36 枚）

**导航（AdminLayout 侧边栏 6 枚）**

| emoji | 图标名 | 形状描述 |
|---|---|---|
| 📊 | `grid-dashboard` | 2×2 圆角块，左上块端点带星点 |
| 👤 | `user-circle` | 圆头 + 肩弧 |
| 📄 | `file-text` | 折角文档 + 两行文字线 |
| 💬 | `message-dots` | 圆角气泡 + 两点 |
| 🤖 | `bot` | 圆角方头 + 双眼点 + 顶点天线 |
| 📈 | `chart-up` | 折线 + 底轴，端点星点 |

**通用操作（全站）**

| emoji / 现状 | 图标名 | 用途 |
|---|---|---|
| ← | `arrow-left` | 返回（独立 icon-btn） |
| ✕ | `close` | 关闭 / 移除 |
| ✚ | `plus` | 新对话 / 新建账号 |
| 🕘 | `history` | 历史对话（圆钟 + 指针） |
| ↻ | `rotate` | 重试 / 再测一次 |
| ⬇ | `download` | 下载 PDF |
| 🔗 | `link` | 分享 / 只读链接 |
| 🚩 | `flag` | 申诉 / 判错了 |
| 📋 | `clipboard` | 剪贴板粘贴 |
| ✍️ | `pen-line` | 粘贴输入 / 编辑 |
| 📄 | `file-text`（复用） | 上传论文 seg、报告选择 |
| ✓ | `check` | 达标、规则通过 |
| ⚠️ | `alert` | 超线、错误空态 |
| 📭 | `inbox-empty` | 无记录空态（开盖信箱） |
| 👍 / 👎 | `thumb-up` / `thumb-down` | 助手回答评价 |
| 🔍 | `search` | 查询 / 可解释支柱 |
| 🧭 | `compass` | 溯源支柱 |
| 🛡️ | `shield` | 救误判支柱 / 验证页 |
| 💬（小白语义） | `xiaobai-spark` | 小白本体：白色圆头轮廓 + 单点青眼睛 + 头顶触角球 + 旁侧四角星，直接复刻 `public/xiaobai.png` 的形象轮廓，双色描边（青 + 渐变蓝星点） |

**助手工具调用 7 枚（AssistantDrawer）**：`chart`（📊）、`folder`（🗂）、`flask`（🧪）、`ruler`（📏）、`book`（📚）、`pen-line`（✍️ 复用）、`tool`（🔧）。

**账号来源 3 枚（AdminUsers）**：`phone`（📱）、`wechat`（💚）、`mail`（📧）。

## 5. 首页大图（Hero）设计

### 5.1 布局

```
┌──────────────────────────── 1080px ────────────────────────────┐
│  eyebrow chip（青 tint 底 + ✦）                                   │
│  h1 46px「看得懂的论文 AI 率检测」                                 │
│  lead 两行                                                      │
│  [✦ 免费检测我的论文](青实心 pill)  [先粘贴一段试试](白底描边 pill)   │
│  灵感 chips：「这段为什么像 AI」「和上次比降了多少」…                  │
│                                            ┌──────────────┐    │
│                                            │  首页大图      │    │
│                                            │  4:3 小白场景  │    │
│                                            └──────────────┘    │
│                                  ┌── 报告卡悬浮，向左叠压大图 ──┐   │
│                                  │ 23.4% · 先改这几段 · 小白批注 │   │
```

- 大图在右侧 `0.8fr` 列，宽高比 4:3，`border-radius: 20px`，无外描边（图片自带留白），底部叠白色渐变以便报告卡压上去；
- 现有 `.hero-card` 报告卡保留，**左移 -60px 悬浮叠压大图左下角**，环境光阴影 §3.4；红/黄绿条改 danger/warning/success 语义色；小白批注行配 `xiaobai-spark` 14px；
- h1 下加 3 个**灵感 chips**（ghost pill，点击直达对应功能）——用大学生的真实场景说话，而不是功能说明书：**「赶 DDL 前自查」**→ /upload、**「导师让我改，改哪里？」**→ /upload?mode=paste、**「答辩前突击查一遍」**→ /verify——这是 ChatGPT 式「建议提示」在营销页的表达；
- hero 文案口语化微调：h1 保持「看得懂的论文 AI 率检测」做 SEO，lead 改为「AI 率是多少、哪几段最像、为什么像、怎么改——小白陪你逐段看懂，别慌，先看懂再动笔。」；
- ≤860px：大图隐藏，chips 换行，报告卡回到单列。

### 5.2 大图规范

- 资产：`web/public/hero/hero-xiaobai.png`（按下方 prompt 生成概念稿，可复现）；
- 构图：**小白站在一摞悬浮的论文旁**，指着摊开文档上被青色高亮的段落；周围点缀四角星点与小对话气泡；背景近白，带青→蓝的极淡渐变光晕；
- 形象一致性：小白必须保持既有特征——纯白球身、青绿触角顶球、耳机侧耳、大圆青眼含星形高光、微笑小嘴、粉腮红（对齐 `public/xiaobai.png`，生成后人工比对修版）；
- 配色锁四色：白 `#FFFFFF`、智能青 `#14B8A6`、辅助蓝 `#3B82F6`、soft coral `#E5484D` 少量点缀（超线段落）；
- 复现 prompt（text_to_image 接口，`image_size=portrait_4_3`）：

```
Cute white spherical AI assistant mascot character with teal cyan antenna,
glowing cyan round eyes and headphone side ears, kawaii chibi style, standing
beside a floating stack of thesis documents, pointing at an open document page
where several paragraphs are highlighted with soft teal marker strokes, small
four-pointed star sparkles and tiny chat bubbles floating around, light airy
near-white background with a very subtle teal to blue gradient glow, minimalist
flat 2.5D vector illustration, soft ambient lighting, generous negative space,
friendly approachable modern AI product mood, restrained palette of white, teal
cyan, cornflower blue, soft coral accents, no text, no letters, no watermark
```

### 5.3 Hero 区其他调整

- eyebrow chip：system-blue tint → `--ai-100` 底 + `--ai-700` 字，前置 ✦ 星点；文案改「免费 · 不代写 · 被误判有路走」；
- 主 CTA 改青实心 pill + `search` 图标，文案「**免费检测我的论文**」；次 CTA 白底描边 pill + `pen-line`，文案「先贴一段看看」；
- 信任行前加 `shield` 小图标（12px，success 色），文案改口语：「本科 20% / 硕士 15% / 博士 10%，按你学校的红线来」；
- h1 关键词「为什么像、哪一段、怎么改」用 `--ai-500` 下划线强调（替代全加粗）。

### 5.4 小白表情包状态图（配套资产）

| 状态 | 表情 | 使用位置 |
|---|---|---|
| 加载中 | 打哈欠（眼半闭） | 检测进行页、骨架屏 |
| 完成 | 比心（双手 + 粉色小心心） | 达标 toast、检测完成 |
| 超线 | 捂嘴（惊） | 结果 hero 超线态 |
| 申诉 | 握拳加油 | 申诉弹窗顶部 |
| 空态 | 摊手 | 各列表空页面 |
| 思考中 | 触角球发光闪烁 | 助手回答生成中 |

表情图用小白现有人设图衍生（同触角球 / 耳机耳 / 星形高光眼），尺寸 64/96px 两档，PNG 透明底，放 `web/public/xiaobai/`。

## 6. 逐页逐按钮规范

> variant 释义：**ai-solid** = 智能青 `--ai-700` 实心白字（12px 圆角 / CTA 用 pill）；**outline** = 1px `--ai-700` 描边透明底；**white-pill** = 白底灰描边 pill（hero 次级）；**ghost** = 无底无边，hover 出 `--ai-100`；**text-link** = 无底无边、青字；**danger** 系列 = `--danger` 红；**success** 系列 = `--success` 绿。图标统一 16px（small 按钮 14px），图标与文字间距 6px，**不再用 emoji 前缀**。
>
> **按钮文案语气**（全站统一）：主 CTA 说结果不说动作——「免费检测我的论文」「先贴一段看看」；次级操作说短话——「重试」「去申诉」；危险操作给情绪缓冲——「删掉这篇？」替代「删除」。禁用「提交 / 执行 / 确认操作」这类系统腔。

### 6.1 Landing

| 按钮 | 旧 | 新 |
|---|---|---|
| 登录 / 进入工作台（导航） | round small | ghost · small · 无图标；「进入工作台」带 `chevron-right` |
| 免费检测我的论文（hero 主 CTA） | primary large round | ai-solid · large(46px) · **pill** · 图标 `search` |
| 先粘贴一段试试（hero 次级） | large round | white-pill · large · 图标 `pen-line` |
| 灵感 chips（新增） | — | ghost · small · pill ·「赶 DDL 前自查」/「导师让我改，改哪里？」/「答辩前突击查一遍」· 图标 `search` / `pen-line` / `shield` |
| 上传报告，让助手带你看（rescue） | primary round | ai-solid · default · 12px · 图标 `file-text` |
| 免费检测我的论文（final） | primary large round | ai-solid · large · 图标 `search` |

支柱卡三图标：🔍→`search`、🧭→`compass`、🛡️→`shield`，24px、青描边圆片底（`--ai-100`）。

### 6.2 Login / Register

| 按钮 | 旧 | 新 |
|---|---|---|
| 密码显示切换（eye 原生 button） | 无图标字符 | icon-btn 28×28 · `eye` / `eye-off`（新增） · ghost |
| 验证码刷新（cap） | 图片点击 | icon-btn 28×28 · `rotate` · ghost，过期态转 danger 红 |
| 模式切换（登录 / 注册） | 文字链接 | text-link · 14px |
| 提交（登录 / 注册） | 自定义 .primary | ai-solid · large(44px) · 全宽 · 10px |
| 左栏价值点 3 项 | emoji | `search` / `compass` / `shield` · 20px |
| 登录页小白元素 | 无 | 左栏底部放小白形象图 + 对话气泡文案（「论文交给我看」），增强 IP 感 |

### 6.3 Dashboard（工作台）

| 按钮 | 旧 | 新 |
|---|---|---|
| + 上传论文（空态 / 头部主 CTA） | primary round large | ai-solid · large · 图标 `file-text`（替代文字里的「+」） |
| 粘贴一段试试 | round large | outline · large · 图标 `pen-line` |
| 表格行：查看 | link primary | text-link · `chevron-right` 图标后缀 |
| 表格行：重试 | link | text-link · 前缀 `rotate` 14px |
| 表格行：删除 | link danger | text-link · danger · 前缀 `close` 14px |
| 空态图（⚠️📭🔎） | emoji | **小白表情包** §5.4：打哈欠（加载）/ 摊手（无记录「还没有记录，交一篇试试？」）/ 疑惑（无匹配「换个词再找找？」）· 96px |
| 「问小白」常驻入口 | FAB（已有） | 保留 FAB，浮起阴影加青色环境光 §3.4，图标换 `xiaobai-spark` |

### 6.4 Upload（上传页）

| 按钮 | 旧 | 新 |
|---|---|---|
| ← 返回 | link 文字箭头 | icon-btn 32×32 · `arrow-left` · ghost（文字「返回」保留可选） |
| seg：📄 上传论文 / ✍️ 粘贴一段 | emoji + 原生 button | segmented control（tokens 已有样式，底色 `--bg-deep`）· 图标 `file-text` / `pen-line` + 文字 |
| 拖拽框整块 | 自定义 dropzone | 拖拽区中心 icon `upload-cloud`（新增，`--ai-500` 32px），边框 1.5px dashed 青，拖入时 `--ai-100` 底 + 发光 §3.4 |
| 更换 | link primary | text-link · `rotate` |
| 移除 | link danger | text-link · danger · `close` |
| 开始检测（主 CTA） | primary round large | **ai-solid · large · pill** · 全宽 · 图标 `search`；未选文件态灰底禁用 |
| 📋 从剪贴板粘贴 | link primary + emoji | text-link · `clipboard` |
| 清空 | link | text-link · `close` |
| 即时检测 | primary round | ai-solid · default · 图标 `flask` |
| 上传全文出报告 | round | outline · default · 图标 `file-text` |

### 6.5 TaskDetail（报告页）

| 按钮 | 旧 | 新 |
|---|---|---|
| ← 返回 | link | icon-btn 32×32 `arrow-left` + 文字 |
| 💬 问助手 / 问助手解读 / 问助手为什么 / 为什么这段像 AI？ | link + emoji | text-link · 前缀 `xiaobai-spark` 14px（助手语义统一走小白图标，青→蓝双色） |
| 🚩 申诉 / 我觉得判错了 | link + emoji | text-link danger · 前缀 `flag` |
| 🔗 分享 / 生成只读分享链接 | link / round + emoji | text-link · 前缀 `link`；底部长条内改为 outline · `link` |
| ⬇ 下载 PDF（头部 / 底部条） | primary round / round + emoji | 头部 ai-solid small · `download`；底部条 outline · `download` |
| 重新检测（失败态） | primary round | ai-solid · default · `rotate` |
| 复制（凭证行 / 段落） | link | text-link · `clipboard` 14px |
| 看段落 | round | outline · `chevron-down`（新增） |
| 全部展开 / 全部收起 | link | text-link · `chevron-up/down` 切换 |
| 为什么（段落行内） | link primary | text-link · `search` 14px |
| ↻ 修改后再测一次 | round + 字符 | outline · `rotate` |
| 💬 让小白点评这次修改 | primary round small + emoji | **ai-solid small · pill** · `xiaobai-spark` |
| 助手提示条关闭 ✕ | link | icon-btn 20×20 · `close` |
| verdict ✓/⚠ | 字符 | `check`（success）/ `alert`（danger）16px |
| 空态 / 失败大图标 ✕ | 字符 | `alert` 40px danger |

### 6.6 Profile / Verify / SharedReport / NotFound / Privacy

| 页面 | 按钮 | 新 |
|---|---|---|
| Profile | ← 返回 | icon-btn `arrow-left` |
| Profile 修改密码弹层 | 取消 / 确认修改 | outline / ai-solid · pill（弹层内） |
| Verify | 验证提交 | ai-solid large 全宽；结果盾牌 ✓/!/✕ → `check` / `alert` / `close`，32px 圆片底（success / warning / danger tint） |
| SharedReport | 去知源免费检测 / 免费检测我的论文 | ai-solid · `search`；页眉加 `shield` 徽标（只读可信） |
| NotFound | 回到工作台 | ai-solid large · `arrow-left` 反转方向 |
| Privacy | ← 返回 | icon-btn `arrow-left` |

### 6.7 AssistantDrawer（小白抽屉）——本次风格的「样板间」

| 按钮 | 旧 | 新 |
|---|---|---|
| 🕘 历史 / ✚ 新对话 / ✕ 关闭 | link + emoji | icon-btn 32×32 · `history` / `plus` / `close` · ghost，hover `--ai-100` |
| 抽屉头部小白身份 | 文字 | `xiaobai-spark` 20px + 「小白」，状态点（在线青 / 生成中呼吸动画） |
| 重试（失败消息） | link primary small | text-link small · `rotate` |
| 停止 / 发送 | default / primary | 发送 = **ai-solid · pill（右半圆）** · `send`（新增纸飞机）· 40×40；流式生成中 → `close` 停止形（outline） |
| 输入框 | el-input | 底色 `--bg-deep`、聚焦环青色、圆角 14px，**胶囊化**（对齐 Kimi / 豆包对话输入） |
| ← 返回（历史列表） | link small | icon-btn 24×24 `arrow-left` |
| 删除（会话） | link small | text-link danger small · `close` |
| 👍 / 👎 | 原生 emoji button | 24×24 icon-btn · `thumb-up` / `thumb-down`，选中态 fill 0.12 自填充 |
| 工具调用行 | TOOL_ICON emoji 7 枚 | §4.3 工具图标，16px 青 |
| 上下文卡 📄 | emoji | `file-text` 16px |
| 达标徽章 ✓ | 字符 | `check` 12px success |
| 回答完成瞬间 | — | sparkle ✦ 250ms 缩放淡入（§3.5） |

### 6.8 FeedbackDialog（申诉弹窗）

| 按钮 | 新 |
|---|---|
| 取消 | outline |
| 提交反馈 | ai-solid · `flag`（申诉语义，danger 文案时用 danger 实心） |

### 6.9 AdminLayout + 6 个后台页

侧边导航：6 枚 §4.3 导航图标（20px，选中态青实底白字圆片）；「← 返回 C 端」→ icon-btn `arrow-left` + 文字；「退出」→ text-link danger + `logout`（新增）。

| 页面 | 按钮 | 新 |
|---|---|---|
| AdminDashboard | 处理（反馈行） | text-link · `flag` |
| AdminUsers | 重置 / 导出 CSV | outline / outline·`download`；＋新建账号 → ai-solid·`plus` |
| | 批量启用 / 批量停用 / 取消选择 | plain success / plain danger / text-link；选中条容器底 `--ai-100` |
| | 详情 / 重置密码 / 编辑 / 保存 / 取消 | text-link / text-link·`rotate` / text-link·`pen-line` / ai-solid small / outline |
| | 停用账号 / 启用账号 / 封禁 / 解封 | plain danger / plain success / text-link danger / text-link |
| | 创建 / 复制账号与密码 | ai-solid pill / ai-solid pill·`clipboard`（弹层保留 pill） |
| | 手机/微信/邮箱标签 | `phone` / `wechat` / `mail` 14px + 文字 tag |
| AdminTasks | 查询 / 重置 / 刷新 / 导出 CSV | ai-solid·`search` / outline / outline·`rotate` / outline·`download` |
| | 批量重试失败 / 批量删除 / 取消选择 | plain warning / plain danger / text-link |
| | 行操作 报告/重试/取消/删除 | text-link · 报告加 `chevron-right`，重试 `rotate` warning，删除 danger |
| | 抽屉：打开报告 / 重试 / 取消 / 删除 | ai-solid / plain warning / outline / plain danger |
| AdminFeedback | 查询 / 重置 | ai-solid·`search` / outline |
| | 统一回复 / 置处理中 / 批量忽略 / 取消选择 | plain 青 / outline / plain 灰 / text-link |
| | 处理 / 查看 | text-link |
| | 确认误判 / 确认是 AI / 拿不准 | small 选中实心：danger / success / 灰 |
| | 快捷模板 chips | ghost small 8px 圆角 |
| | 保存 / 取消 | ai-solid·`check` / outline |
| | 复核行 误判 / 是 AI / 拿不准 | text-link danger / success / 灰 |
| AdminAssistant | 刷新 / 查询（×3 tab）/ 重置 | outline·`rotate` / ai-solid·`search` |
| | 转成知识 / 编辑 / 新增 / 热加载 / 质检 | text-link·`book` / text-link·`pen-line` / ai-solid·`plus` / outline·`rotate`（危险确认） / text-link |
| | 保存标注 / 保存并热加载 / 取消 | ai-solid / ai-solid·`rotate` / outline |
| AdminAnalytics | 查询 / 重置 / 重算统计 | ai-solid·`search` / outline / outline·`rotate`；行操作「查看」text-link·`chevron-right` |

### 6.10 Element Plus 全局观感（tokens.scss 组件区）

- 按钮：`border-radius: 10px`，`font-weight: 500`；primary plain tint 改 `--ai-100`；round/pill 规则按 §3.3 收敛；
- 输入框：底色 `--bg-deep`，聚焦环 `0 0 0 2px rgba(15,118,110,0.20)`；
- 表格：行 hover `--ai-100`；表头保持 12px 大写间距；
- Tag：8px 圆角（去 pill），状态色映射 §3.1；
- Progress：红/黄/绿条 → danger / warning / success；
- Radio 组（segmented）：底色 `--bg-deep`，选中白块描边 `rgba(23,24,28,0.10)`。

## 7. 实施拆解与验收

| 阶段 | 内容 | 涉及文件 |
|---|---|---|
| P1 令牌 | tokens.scss 全量替换 + EP 组件区改写 | `web/src/styles/tokens.scss` |
| P2 图标 | vite-plugin-svg-icons + ZyIcon 组件 + 36 枚 SVG + 全站 emoji 替换 | `web/src/components/icons/**`、各页 |
| P3 首页 | hero 大图 + 灵感 chips + 报告卡重绘 + 支柱卡图标 + CTA | `views/Landing.vue`、`public/hero/` |
| P4 C 端 | Login / Dashboard / Upload / TaskDetail / Profile / Verify / SharedReport / NotFound / Privacy + AssistantDrawer / FeedbackDialog | 对应 views / components |
| P5 后台 | AdminLayout + 6 页 | `layouts/AdminLayout.vue`、`views/admin/*` |

**验收清单**

1. `grep` 全站无 emoji 图标残留（🚩💬🔗⬇🕘✚ 等 §4.3 列出的全部字符）；
2. 主色 token 全局仅 `--ai-700` 一个来源，无硬编码 `#007AFF` 残留；
3. `#0F766E` / `#E5484D` 对白底对比度 ≥ 4.5:1（正文）；`#14B8A6` 不用于正文文字；
4. pill 仅出现在 §3.3 列出的对话/转化场景；
5. hero 大图小白形象与 `public/xiaobai.png` 特征一致（触角球、耳机耳、星形高光眼）；
6. 小白表情包 6 枚（§5.4）落位：空态 / 加载 / 超线 / 申诉 / 完成 / 思考中，每个状态有情绪、有口语文案，无「尊敬的用户 / 请勿 / 您」字样；
7. 首页 Lighthouse：hero 大图带 `width/height` 防跳动；sparkle / 弹簧 / 呼吸动效在 `prefers-reduced-motion` 下全部关闭；
8. `npm run typecheck` 通过；860px 断点下 hero、导航、表格不破版。
