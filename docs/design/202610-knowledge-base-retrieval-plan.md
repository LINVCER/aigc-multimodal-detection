# 知识库检索演进方案：BM25 → 向量检索

> 日期：2026-10
> 范围：论文检测助手知识库（`deploy/inference-python/assistant/knowledge/`）的检索与存储升级
> 状态：方案评审中 · 未实施

---

## 0. 结论先行

| 项 | 现状 | 结论 |
|---|---|---|
| 规模 | 7 篇 39 块，约 1.2 万字 | 距离「需要向量库」还差 1~2 个数量级 |
| 检索 | 内存 BM25 + 倒排索引 | **176 微秒/次**，已是微秒级，非瓶颈 |
| embedding 来源 | 无 | **DeepSeek 不提供 embedding 端点**，是硬阻塞 |
| 向量存储 | 无 | **MySQL 8 无原生向量索引**，写库只会更慢 |

**推荐路线**：短期保持 BM25（已完成倒排索引优化）；中期按需做「内容入库 + 内存 BM25」；**只有当知识块规模或语义召回成为真实痛点时，才上向量检索**，且必须另配 embedding 来源。

---

## 1. 问题定义

### 1.1 原始诉求（拆解后）

1. 「向量知识库引用更快」→ 认为向量检索更快；
2. 「写入数据库」→ 希望知识持久化、可运营管理；
3. 「每次提问都要扫一遍文件」→ 担心检索有重复 IO / 全量扫描开销。

### 1.2 已澄清的技术事实

- **不是扫文件**：`reload()` 只在服务启动 / 手动 `/knowledge/reload` 时读一次磁盘；每次提问是内存遍历（`search()`）。
- **检索不是瓶颈**：实测 176 微秒/次（12000 次 2.12s），相对 DeepSeek 对话（首 token 数百毫秒起）占比 <0.1%。
- **DeepSeek 无 embedding**：官方确认无 embedding 端点（[DeepSeek-V3 #806](https://github.com/deepseek-ai/DeepSeek-V3/issues/806)）。向量化必须另找 embedding 来源。
- **MySQL 8 无向量索引**：`VECTOR` 类型与向量索引是 MySQL 9.0 才引入；项目锁 MySQL 8，只能 JSON 列存数组 + 应用层逐行算余弦，比内存 BM25 慢几个数量级。

---

## 2. 方案对比（4 选）

| 维度 | A. BM25 + 倒排索引（现状） | B. 内容入库 + 内存 BM25 | C. 真向量检索 | D. 混合检索（BM25 召回 + 向量 rerank） |
|---|---|---|---|---|
| 原理 | 词频统计，关键词匹配 | 同 A，但数据落 MySQL | embedding 余弦相似度 | 先 BM25 粗召回，再向量精排 |
| embedding 依赖 | 无 | 无 | **必须有**（另配） | **必须有** |
| 存储 | Markdown 文件 | MySQL `knowledge_chunk` 表 | MySQL JSON 向量列 / 向量库 | 同 C |
| 单次检索耗时 | ~0.18ms | ~0.18ms | 数十~数百 ms（含 embedding） | 同 C |
| 语义召回（关键词对不上也能中） | ❌ | ❌ | ✅ | ✅ |
| 运营改知识 | 改 md + reload | 改数据库 | 改数据库 + **重算向量** | 同 C |
| 复杂度 / 依赖 | 最低 | 低 | 中高 | 高 |
| 适用规模 | < 500 块 | < 500 块 | 1000+ 块 / 明确要语义 | 1000+ 块 |

**关键判断**：当前 39 块，A 是最优解；B 满足「入库」诉求但不改变检索；C/D 的价值只在规模或语义需求到来后才显现，且引入 embedding 依赖 + 向量维护成本。

---

## 3. embedding 来源选型（若走 C/D 才需要）

| 方案 | 模型 | 维度 | 中文 | 成本 | 依赖 |
|---|---|---|---|---|---|
| DashScope API | `text-embedding-v3` | 512/768/1024 可调 | 强 | 按量（有免费额度） | 需 `DASHSCOPE_API_KEY`，网络调用 |
| 本地模型 | `bge-small-zh-v1.5` | 512 | 强 | 0 元 | 数百 MB 权重 + torch，占内存/显存 |
| 本地模型 | `bge-m3` | 1024（稠密+稀疏） | 强 | 0 元 | 更大权重，可兼做稀疏检索 |
| OpenAI | `text-embedding-3-small` | 1536 | 一般 | 按量 | 需 OPENAI key |

**倾向**：中文场景 + 已有 DeepSeek 的情况下，若必须向量化，**本地 `bge-small-zh-v1.5` 或 DashScope `text-embedding-v3`** 是首选——二者中文都好，前者零成本零网络依赖，后者零权重负担。

---

## 4. 向量存储选型（若走 C/D）

| 方案 | 检索方式 | 说明 |
|---|---|---|
| MySQL JSON 列 | 应用层全表余弦 | 满足「写数据库」但最慢；39 块尚可，1000 块不可接受 |
| SQLite + faiss（内存） | faiss 暴力/IVF | 快，但脱离 MySQL，需另建索引文件 |
| pgvector | 原生向量索引 | 要换 Postgres，项目锁 MySQL，不现实 |
| Milvus / Qdrant | 专用向量库 | 单机过度设计，多一个重型服务 |

**倾向**：单机 + MySQL 约束下，若坚持「向量写进 SQL」，只能接受 **MySQL JSON + 应用层余弦**；若追求真实向量性能，则需放弃 MySQL 用 **faiss/SQLite**，二者不可兼得。

---

## 5. 目标方案（若最终走「内容入库」）

### 5.1 表结构（方案 B，最小改动）

```sql
CREATE TABLE knowledge_chunk (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  doc          VARCHAR(64)  NOT NULL,          -- 如 07-verification
  title        VARCHAR(128) NOT NULL,          -- 块标题
  tags         VARCHAR(255) DEFAULT '',        -- 逗号分隔
  body         TEXT         NOT NULL,          -- 块正文
  sort_order   INT          NOT NULL DEFAULT 0,
  enabled      TINYINT      NOT NULL DEFAULT 1,  -- 运营可下线某块
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_doc (doc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- SQL 文件按项目规范走 `docs/releases/sql/V{ver}__init_knowledge_chunk.sql`（Flyway 风格）+ `R__seed_knowledge_chunk.sql`（幂等 seed，从现有 7 篇 md 导入）。
- **检索仍用内存 BM25**：服务启动时 `SELECT` 全表进内存建倒排索引，`reload()` 改为从 DB 读。既持久化、可后台运营编辑，又保持微秒级检索。

### 5.2 若叠加向量（方案 C/D，仅在规模触发后）

- `knowledge_chunk` 增加 `embedding JSON` 列（float 数组）；
- 建库脚本：md → 切块 → 调 embedding → 写回 DB；
- 查询：`embedding(query)` → 与命中块算余弦 → top-k；
- 混合检索（推荐 D）：**BM25 粗召回 top-20 → 向量精排 top-3**，兼顾关键词精准与语义召回，是 RAG 业界标准姿势。

---

## 6. 分期路线（推荐）

| 阶段 | 做什么 | 触发条件 | 状态 |
|---|---|---|---|
| Phase 0 | BM25 + 倒排索引 | 已做（本次） | ✅ |
| Phase 1 | 内容入库 + 内存 BM25（方案 B） | 需要后台运营可编辑知识、或知识脱离代码仓库管理 | 待决策 |
| Phase 2 | 向量检索（方案 C 或 D） | 知识块 > ~500 且语义召回成为真实痛点 | 待触发 |

---

## 7. 需要你拍板的输入

1. **Phase 1 要不要做**：是否希望知识块从「Markdown 文件」迁移到「MySQL 表 + 后台运营可改」？
2. **若最终要向量**：embedding 来源选哪个——本地 `bge-small-zh-v1.5`（零成本）还是 DashScope `text-embedding-v3`（需 key）？
3. **向量存储口径**：坚持「写进 MySQL」就接受慢；要快就得接受 faiss/SQLite 脱离 MySQL。

> 建议：先只做 Phase 1（内容入库，检索仍 BM25，满足「写数据库」），把向量化留到规模真到了再决策。这样既回应了「入库」诉求，又不背上当前不必要的 embedding 复杂度。
