# 知源小白视觉素材缺口清单

> 2026-10 · 配套 `202610-web-visual-style-prompt.md` / `202610-web-visual-redesign-plan.md`。
> App 端主题已按 style-prompt 落地（`mobile-uniapp/uni.scss`、`components/ZyIcon.vue`、`components/EmptyState.vue`），
> 代码侧已留好挂点，下面列的是**还没有的素材**：谁来出、什么规格、放哪、代码里怎么接。

## 1. 现有素材盘点

| 文件 | web | App | 用途 | 问题 |
|---|---|---|---|---|
| `xiaobai.png` | `web/public/` | `mobile-uniapp/static/` | 小白人设主图 | 1.19 MB，App 内用作空态顶替图偏大 |
| `xiaobai.gif` | `web/public/` | `mobile-uniapp/static/` | FAB 常驻动图 | 405 KB，无 reduce-motion 静帧 |
| `logo.png` / `logo-mark.png` | 有 | 有 | 品牌字标 / 图标 | `logo.png` 1.1 MB，未裁 2x/3x |
| `icon-1024.png` | — | 有 | App 启动图标 | manifest 各 dpi 全指同一张 1024 图 |
| `ai_tag.png` | — | 有 | 旧「AI 标签」图 | 917 KB，当前页面已无引用，可删 |
| `favicon-32 / icon-192 / icon-512 / apple-touch-icon` | 有 | — | PWA / 收藏夹 | 正常 |

两端都没有：表情包、hero 插画、启动页、分享图、SparkLine 独立 SVG 文件。

## 2. 缺口清单（按优先级）

### P0 · 小白表情包六态

style-prompt C6「IP 情绪状态机」是硬验收项，目前 App 空态用 `xiaobai.png` 顶替，六个状态长一个样。

| 状态 | 表情 | 文件名 | App 挂点 | web 挂点 |
|---|---|---|---|---|
| 空态 | 摊手 | `xiaobai-shrug` | `EmptyState mood="shrug"`（默认）；首页 / 列表无记录 | 列表空页 |
| 加载中 | 打哈欠、眼半闭 | `xiaobai-yawn` | 检测进行页、骨架屏 | 同 |
| 完成达标 | 比心，双手 + 粉色小心心 | `xiaobai-heart` | 结果 hero 达标态、toast | 同 |
| 超线 | 捂嘴、惊 | `xiaobai-cover` | 结果 hero 超线态 | 同 |
| 申诉 | 握拳加油 | `xiaobai-fist` | 申诉 / 反馈弹层顶部 | 同 |
| 思考中 | 触角球发光闪烁 | `xiaobai-think` | 小白对话页回答生成中（现用 gif） | 同 |

规格
- 形象锁死：纯白球身、青绿触角顶球、耳机侧耳、大圆青眼含星形高光、微笑小嘴、粉腮红，比对 `xiaobai.png` 人工修版，不许变形。
- 配色锁四色：白 `#FFFFFF`、智能青 `#14B8A6`、辅助蓝 `#3B82F6`，比心的心心用腮红粉 `#FF9EB5`，其余不出现第二主色。
- 尺寸：PNG 透明底，App 出 192 / 288 px 两档（对应 96 pt @2x / @3x），web 出 64 / 96 px；总大小每张控制在 40 KB 内。
- `xiaobai-think` 额外出一版 Lottie 或 APNG 做触角闪烁，另给一张静帧供 `prefers-reduced-motion`。
- 落位：web `web/public/xiaobai/`，App `mobile-uniapp/static/xiaobai/`。

接入方式：`components/EmptyState.vue` 的 `MOOD_SRC` 映射改指新文件即可，调用方已按 `mood` 传值。

### P0 · 启动图 / App 图标分辨率套图

- `manifest.json` 的 Android hdpi ~ xxxhdpi 与 iOS @2x/@3x 全部指向同一张 `icon-1024.png`，HBuilderX 云打包会原图压缩，边缘发虚。
- 需要：以 `logo-mark.png` 为母版，底色暖白 `#FAF9F6`、图标智能青，按 uni-app 规格出 72 / 96 / 144 / 192、120 / 180、1024 共七张；iOS 另出 Launch Storyboard 用的 `splash@2x / @3x`。
- 落位：`mobile-uniapp/static/icons/`，改 `manifest.json` 对应路径。

### P1 · Hero 插画（web 首页，App 首页可降级复用）

- 文件：`web/public/hero/hero-xiaobai.png`，4:3 竖构图，另出 `hero-xiaobai@mobile.webp`（≤ 120 KB）给 App 首页 hero 卡做背景。
- 构图与生成 prompt 已写在 `202610-web-visual-redesign-plan.md` §5.2，生成后按人设图修版。
- App 侧挂点：`pages/home/home.vue` hero 卡右侧留白位，现为纯色。

### P1 · 现有图资源瘦身

| 文件 | 现状 | 目标 |
|---|---|---|
| `xiaobai.png` | 1.19 MB | 出 192 / 288 / 384 px 三档 PNG，每张 ≤ 60 KB；原图移到 `docs/design/assets/` 存档 |
| `xiaobai.gif` | 405 KB | 换 Lottie JSON（≤ 30 KB）或 APNG；补静帧 `xiaobai-still.png` |
| `logo.png` | 1.1 MB | 导出 SVG + 2x PNG（宽 408 px）两份 |
| `ai_tag.png` | 917 KB，已无引用 | 删除 |

App 首包体积目前被这四张图占掉约 3.5 MB，瘦身后预计首包减 3 MB。

### P2 · SparkLine 图标 SVG 源文件

- 现状：App 端 `ZyIcon.vue` 把 30 余枚图标以 path 字符串内联，web 端规划走 `vite-plugin-svg-icons` 读 `web/src/components/icons/svg/*.svg`。两端缺一份共同的 SVG 源。
- 需要：按 redesign-plan §4.3 的 36 枚清单，每枚一个 24×24 SVG，`stroke-width 1.75`、圆头圆角、末端四角星点；设计稿里单独标出 `xiaobai-spark` 的双色版。
- 落位：`docs/design/assets/sparkline/`，作为两端唯一源；App 端后续用脚本从 SVG 生成 `ZyIcon.vue` 的 `ICONS` 表，避免手抄。
- 缺口：`eye` / `eye-off` / `logout` 三枚在 App 端尚未内联，登录页密码切换仍用文字。

### P2 · 分享 / 溯源图

- 结果页「分享报告」与 PDF 封面溯源区需要一张 1200×630 OG 图（小白 + 「这份报告可溯源」）和一张 PDF 封面小白水印 PNG（灰度、透明底、≤ 20 KB）。
- 落位：`web/public/og/`、`backend-java/.../resources/pdf/`。

## 3. 交付约定

- 文件名全小写 ASCII，连字符分词，不带中文、空格、尺寸后缀以 `@2x` / `@3x` 结尾。
- 每批素材附一张总览图放到 `docs/design/assets/preview/`，方便评审对齐人设。
- 素材到位后代码侧只改路径表：`EmptyState.vue MOOD_SRC`、`manifest.json icons`、`home.vue hero` 三处，不动版式。

## 4. 验收

1. 六态表情包落位后，App 空态 / 加载 / 完成 / 超线 / 申诉 / 思考六个页面各能看到对应表情，且文案无「尊敬的用户 / 请勿 / 您」。
2. `manifest.json` 各 dpi 指向独立尺寸文件，云打包后桌面图标边缘清晰。
3. `mobile-uniapp/static/` 总大小 ≤ 1 MB。
4. `prefers-reduced-motion` 下 FAB 与思考态显示静帧，无动图。
