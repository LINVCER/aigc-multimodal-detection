# highschool-spider

高校公开页学位论文红线爬虫（礼貌版）。帮用户查到**自己学校对学位论文 AIGC 率 / 查重率的要求**，
产出结构化候选供后台人工审核，落 `edu_school_rule`（见 `docs/design/202610-school-redline-plan.md`）。

## 它做什么

1. 读 `seeds.csv` 里各高校研究生院 / 教务处的通知列表页；
2. 在该校 `edu.cn` 域内，按关键词（通知 / 学位论文 / AIGC / 查重 …）有限深度跟进；
3. 命中含阈值的通知时，抽出候选：学位、指标（AI 率 / 查重率）、百分比、检测平台、届别、原文片段、来源 URL、置信度；
4. 写出 `out/candidates.jsonl` 与 `out/candidates.csv`，**全部 status=pending**，交后台人工核对 snippet 与来源后才入库。

## 它不做什么（硬约束，勿改）

- 不碰任何需要登录 / 验证码 / 付费的页面，**不绕过任何鉴权**；
- **不抓知网 / 维普 / 万方**等检测平台，只抓高校自己的公开通知；
- 遵守 `robots.txt`（含 `Crawl-delay`）；每域限速、限页数、限深度；只在 seed 所属 edu.cn 域内爬；只读 HTML，不提交表单；
- 产出只是「候选 + 证据」，不是判定，最终以人工核对的官方文件为准。

## 结构（借 spider-v2 的分层与每站适配器思路）

```
highschool-spider/
  spider.py          # CLI 调度：按 seed 选适配器、BFS 抓取、写出候选
  fetcher.py         # 公共抓取层：robots 合规 + 每域限速 + 取页 + 正文/链接解析
  extract.py         # 通用红线抽取规则（可单独自测）
  adapters/
    __init__.py      # 注册表 get_adapter(seed)，默认走 generic
    base.py          # SiteAdapter 基类 + GenericAdapter（关键词驱动）
  seeds.example.csv  # 种子格式示例
  requirements.txt
```

某所学校页面结构特殊（列表要翻页、正文在固定容器、入口是 JS 列表）时，在 `adapters/` 下建 `<school>.py`
写 `SiteAdapter` 子类覆盖 `seed_urls / should_follow / extract`，在 `adapters/__init__.py` 的 `_REGISTRY` 注册即可，
其余学校继续走 `generic`。这与 spider-v2 的 `platforms/<name>/` 一样：通用链路固定，站点差异下沉到适配器。

## 用法

```bash
pip install -r tools/highschool-spider/requirements.txt

# 离线自测（不联网）
python tools/highschool-spider/spider.py --selftest

# 预演：只打印将访问的入口，不发真实请求
python tools/highschool-spider/spider.py --seeds tools/highschool-spider/seeds.example.csv --dry-run

# 实跑（请自备 seeds，建议 delay≥4s，先小批）
python tools/highschool-spider/spider.py --seeds my_seeds.csv --out out --delay 5 --max-pages 40 --cache-dir out/cache
```

参数：`--delay` 每域最小间隔秒、`--depth` 跟进深度、`--max-pages` 每校页数上限、`--cache-dir` 缓存 HTML 便于离线调规则。

## 输出与入库

`candidates.csv` 列：`school_id, school_name, degree_type, metric, limit_pct, platform, effective_year, confidence, source_url, snippet`。

人工复核流程：按 `confidence` 降序看，核对 `snippet` 与打开 `source_url` 确认是官方文件，确认后在后台「学校与红线」把该候选发布为 `edu_school_rule`（`source_type=official`，带 `source_url`）。低置信或无法核实的丢弃。

## 注意

- 高校站点常用 GBK，已自动判编码；个别站点反爬严格时请增大 `--delay` 或减小 `--max-pages`，不要并发猛拉。
- 抽取是启发式的，AI 率与查重率同句出现时可能各出一条，**务必人工看 snippet 再定**。
- 本工具只收集公开政策信息，不采集任何学生个人数据或论文正文。

## 深挖模式 `--deep`

公开通知页常把阈值藏在二级列表、翻页、研究生院/教务处子站，或**附件红头文件（PDF/DOC）**里。`--deep` 会：

- 把默认深度 2→4、每校页数 50→150（显式传参则不覆盖）；
- 跟进列表翻页（`index_2.html` / `?page=2` 等）与同校 `gs.` / `yjs` / `jwc` 子站；
- 下载并解析 PDF / DOCX / DOC 附件正文（需 `pip install pypdf python-docx`，缺库自动跳过）；
- 仍然遵守 robots.txt 与每域限速，不碰任何鉴权。

```bash
python tools/highschool-spider/spider.py --seeds my_seeds.csv --out out --deep --delay 2 --max-attachments 10
```

输出除 `candidates.{jsonl,csv}` 外，`--deep` 命中页还写 `out/pages.jsonl`，含每页**基本信息**：
通知标题、发布日期、检测平台、适用范围（全日制/专硕…）、送检次数、是否免费、归口部门，供人工复核时了解背景。

### robots 与 UA 说明

- robots.txt 由本工具用统一 UA 自取再解析：无 robots（404）按允许，真实 `Disallow` 照禁。
  这样可避免高校反爬对默认 urllib UA 回 403、被误判成「整站禁止」。
- UA 为纯 ASCII（HTTP 头不能带中文），标明用途与联系方式。

### 提示：不是每所学校都公开数字

部分高校（尤其顶尖院校）只在内部红头文件里给 AIGC/查重阈值，公开页查不到数字。
这类学校靠用户上报 + 通用口径兜底（见 `docs/design/202610-school-redline-plan.md` §3、§5），爬虫抓不到属正常。

## 新增一所学校的操作流程（每校一个适配器）

爬取不是对所有学校用一套盲爬，而是**一校一确认、一校一脚本**：

1. **人工确认**：打开该校研究生院/教务处网站，看清楚——学位论文检测通知在哪个栏目、阈值是写在正文还是附件红头文件、用什么检测平台、适用哪些学位；
2. **写适配器**：复制 `adapters/example_school.py` 为 `adapters/<school>.py`（如 `nwpu.py`），改 `name / match / seed_urls / should_follow`，正文结构特殊时再覆盖 `extract`；入口 `seed_urls` 直接给确认过的通知列表页，比从首页逛高效；
3. **注册**：在 `adapters/__init__.py` 的 `_REGISTRY` import 并 append；
4. **验证后提交爬取**：先用该校一行的 seeds 跑 `spider.py --deep` 看候选对不对，OK 再提交到爬取器（批量离线，或后台按需触发）。

没写专属适配器的学校自动走 `generic`（关键词盲爬），作兜底；写了适配器的学校走各自精确策略。
后台「爬取种子」表的 `adapter` 字段记录每所学校用哪个适配器，与此一一对应。
