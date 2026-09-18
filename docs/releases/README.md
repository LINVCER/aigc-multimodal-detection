# docs/releases/ · 版本文档中心

产品的每次发版（不管是后端 / 前端 / DB schema / 模型）都在这里留一份档，走规范化路线。
比散落在 commit message 和 chat 里更耐存 —— 半年后回溯只看这里。

## 目录结构

```
docs/releases/
├── README.md               ← 本文（规范说明）
├── CHANGELOG.md            ← 顶层滚动变更日志（每版一段摘要）
└── v{X.Y.Z}/               ← 每个版本一个目录
    ├── release-notes.md    ← 版本说明（Added / Changed / Fixed / Breaking / Known Issues）
    ├── migration.md        ← 升级手册（人类可读的升级步骤）
    └── sql/                ← DB 变更（Flyway 规范命名，可脚本化自动跑）
        ├── V{X.Y.Z}.NNN__desc.sql   ← 增量迁移（一次性）
        └── R__desc.sql              ← Repeatable（每次部署都跑，如 seed 数据）
```

## SQL 命名规范（Flyway 风格）

| 前缀 | 含义 | 命名示例 |
|---|---|---|
| `V` | Versioned · 一次性增量迁移，按序号执行 | `V0.1.0.001__init_baseline_schema.sql` |
| `R` | Repeatable · 每次部署都跑（幂等），常见于 seed / view / stored proc | `R__seed_scenario_threshold.sql` |
| `U` | Undo · 回滚脚本（可选，慎用） | `U0.1.0.001__drop_baseline_schema.sql` |

- 版本号中的 `.NNN` 是同一版本内的执行序号（001/002/003…）
- 描述用 `snake_case`，简短表明动作
- 一个文件只做一件事，方便回滚定位

## 版本号规范（对齐语义化 SemVer）

- `major`：破坏性 API / 表结构变更 → +1
- `minor`：新功能兼容旧调用 → +1
- `patch`：只修 bug / 补索引 / 调超参 → +1

版本号统一贯穿：git tag、release-notes、SQL 迁移前缀、模型 ml/VERSIONS.md。

## 每次发版流程

1. 建 `docs/releases/v{X.Y.Z}/` 目录
2. 写 `release-notes.md`（模板见 `v0.1.0/release-notes.md`）
3. 增量 SQL 放 `sql/V{X.Y.Z}.NNN__*.sql`；幂等 SQL 放 `sql/R__*.sql`
4. 复杂升级操作写 `migration.md`
5. 在 `CHANGELOG.md` 顶部追加一行摘要
6. `git tag v{X.Y.Z}` 打标签
7. 生产走 Flyway/自研脚本按序执行 sql/ 下所有文件

## 与其它规范文档的关系

- **`ml/VERSIONS.md`**：模型版本登记（跟发版可能不同频，模型可以独立迭代）
- **`docs/database/scripts/`**：留作历史脚本归档，新脚本一律走 `docs/releases/*/sql/`
- **`backend-java/scripts/patch-schema.sql`**：留作"当前累计的全量 schema 快照"便于一键搭本地，
  不再增量堆积；未来所有增量走 `docs/releases/*/sql/`
