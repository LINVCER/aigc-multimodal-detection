# 检测数据分析与分类筛选方案（后台）

> 日期：2026-10
> 范围：把所有用户检测数据做多维分析、分类筛选、落库，供后台运营参考
> 现状痛点：`DetectTaskServiceImpl.statistics()` 用 `findAll()` 全表内存聚合，量一大就崩，且结果不落库、不可按维度筛选
> 状态：P0 已按推荐方案落地（2026-10-07：物化表 + 提交时增量 + rebuild 兜底 + 后台「检测分析」页 + 明细筛选增强）；P1 CSV 导出 / 定时重算、P2 灰度对比 / 申诉合理率待做

---

## 0. 现状：明细已入库，缺「分析层」

`detect_task` 表**已经存了所有用户的检测明细**，字段足以支撑多维分析：

| 已有字段 | 可作分析维度 |
|---|---|
| `scenario` | 场景（本科/硕士/博士/职业报告/自媒体/其他） |
| `status` | 状态（DONE/FAILED/PENDING） |
| `ai_rate` | AI 率（可分桶） |
| `threshold` | 红线快照（算达标/超线） |
| `source_labels_json` | 溯源分布 |
| `model_version` | 模型版本（灰度对比） |
| `created_at` / `finished_at` | 时间（天/周/月） |
| `user_id` | 用户（Top 用户/活跃度） |

**结论**：不需要再造数据，缺的是「把明细聚合成分类统计、落库、可筛选展示」的分析层。

---

## 1. 分析维度（分类筛选的 8 个切面）

| 维度 | 取值 | 说明 |
|---|---|---|
| 时间 | 天 / 周 / 月 / 自定义区间 | 主聚合轴 |
| 场景 | 6 类 + 全部 | 各学位/场景红线不同，分开看才有意义 |
| 状态 | DONE / FAILED / PENDING | 区分「完成」与「异常」 |
| AI 率分桶 | 0-10 / 10-20 / 20-30 / 30-50 / 50-100 | 看分布形态 |
| 达标 | 达标（≤红线）/ 超线（>红线） | 核心业务指标 |
| 溯源 | human / gpt / qwen / deepseek / … | 哪家 LLM 占比高 |
| 模型版本 | 版本标签 | 模型灰度前后对比 |
| 用户 | Top 用户 / 检测频次 | 活跃度与异常识别 |

---

## 2. 分析指标

| 指标 | 定义 | 用途 |
|---|---|---|
| 检测量 | count(DONE) | 规模 |
| 平均 AI 率 | avg(ai_rate) | 整体水平 |
| 达标率 | 达标 / DONE | 健康度 |
| 超线率 | 超线 / DONE | 风险面 |
| 溯源占比 | source_labels 归一 | 哪家 LLM 是主要来源 |
| 高危段落占比 | calibrated_prob≥0.7 段 / 正文段 | 需 JOIN 段落表，可选 |
| 申诉合理率 | appeal 且「认定合理」/ 申诉 | 误判率（衔接模型 backlog） |

---

## 3. 落库设计

### 3.1 明细库（已有，不动）

`detect_task` 已是全量明细，作为分析的事实来源。

### 3.2 统计表（新增，物化聚合结果）

```sql
-- 按「天 × 场景 × 状态」物化的统计快照，后台直接读表，不用每次 GROUP BY 全表
CREATE TABLE IF NOT EXISTS detect_statistics_daily (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  stat_date          DATE NOT NULL,
  scenario           VARCHAR(32) NOT NULL DEFAULT 'all',   -- 'all' = 全场景
  status             VARCHAR(16) NOT NULL DEFAULT 'all',   -- 'all' = 全状态
  total_count        INT NOT NULL DEFAULT 0,               -- 该分片检测量
  done_count         INT NOT NULL DEFAULT 0,
  avg_ai_rate        DECIMAL(5,2) NULL,
  pass_count         INT NOT NULL DEFAULT 0,               -- 达标数
  over_count         INT NOT NULL DEFAULT 0,               -- 超线数
  source_labels_json JSON NULL,                            -- 溯源分布聚合
  updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_scenario_status (stat_date, scenario, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '检测数据按天×场景×状态物化统计';
```

### 3.3 为什么物化（落库）而不是实时聚合

- 后台看板要「秒开」，实时 `GROUP BY` 全表在几十万任务后会变慢；
- 物化后可按 `stat_date` 范围快速查询趋势，也能被「误判率分析」「模型灰度对比」复用；
- 明细表仍在，统计表只是「参考快照」，可重算、可回溯。

---

## 4. 聚合逻辑（两种，分期）

| 方案 | 做法 | 适用 |
|---|---|---|
| **A. 定时重算**（推荐） | 每日凌晨用 SQL 聚合「昨天 + 最近 30 天」，`REPLACE INTO` 统计表 | 数据量起来后 |
| **B. 触发式增量** | 每次检测 DONE 后，`UPDATE` 当天分片计数 | 实时性要求高 |

> 当前数据量小（几十条），**先做 B（提交时增量更新当天行）** 即可，逻辑简单；量大了切 A（定时全量重算）。

---

## 5. 后台展示（「检测分析」页）

```
┌──────────────────────────────────────────────┐
│ 筛选器：时间区间 [日历] 场景 [下拉] 状态 [下拉]    │
│         AI率区间 [下拉] 达标 [全部/达标/超线] 模型[下拉]│
├──────────────────────────────────────────────┤
│ KPI 卡：检测量 | 平均AI率 | 达标率 | 超线率      │
├──────────────────────────────────────────────┤
│ 趋势折线：30天检测量 + 平均AI率（双轴）           │
├──────────────────────────────────────────────┤
│ 分布：场景柱状 | AI率分桶直方 | 溯源堆叠         │
├──────────────────────────────────────────────┤
│ 明细表：按筛选条件列出检测任务（标题/用户/AI率/    │
│         场景/达标/时间），可导出 CSV             │
└──────────────────────────────────────────────┘
```

- 趋势/分布读**统计表**（快）；明细表查 `detect_task`（带筛选条件 SQL）；
- 明细导出 CSV（运营参考，非批量导出论文，不触碰「不做批量导出」红线——导出的是**统计明细行**，不是论文文件）。

---

## 6. 接口设计（`/admin/**`，Sa-Token）

| 接口 | 说明 |
|---|---|
| `GET /admin/detect/analytics?dateFrom&dateTo&scenario&status&rateBucket&pass&modelVersion` | 返回 KPI + 趋势 + 分布（读统计表） |
| `GET /admin/detect/tasks`（增强筛选） | 明细列表，加 scenario/rateBucket/pass/modelVersion 筛选 |
| `GET /admin/detect/tasks/export` | 明细 CSV 导出 |
| `POST /admin/detect/statistics/rebuild` | 手动触发统计表重算（`REPLACE INTO`） |

---

## 7. 分期

| 阶段 | 内容 |
|---|---|
| **P0** | 统计表 + SQL 聚合 + `GET /admin/detect/analytics`（KPI/趋势/场景分布）+ 明细筛选增强 |
| P1 | AI 率分桶直方 + 溯源堆叠 + CSV 导出 + 触发式增量更新 |
| P2 | 定时重算任务（若依 XXL-Job/snail-job）+ 模型版本灰度对比 + 申诉合理率接入 |

---

## 8. 需要你拍板

1. **落库方式**：物化统计表（`detect_statistics_daily`，后台秒开）——同意吗？还是想直接实时 SQL 聚合不落统计表（更简单，但数据量大后变慢）？
2. **明细导出 CSV** 要不要这次做（运营参考用，导出的是统计行不是论文文件）？
3. **聚合时机**：先做「提交时增量更新」还是「每日定时重算」？
