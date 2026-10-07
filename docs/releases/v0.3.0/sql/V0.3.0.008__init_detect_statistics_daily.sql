-- ============================================================
-- V0.3.0.008 · 检测数据按天 × 场景 × 状态物化统计（detect-analytics-plan §3.2）
-- 维度值 'all' 表示不分该维；每个任务事件写 4 行：(all,all) (sc,all) (all,st) (sc,st)
-- ai_rate_sum 是为了增量更新平均值（avg = ai_rate_sum / done_count），方案表里没有、这里补
-- 幂等
-- ============================================================

CREATE TABLE IF NOT EXISTS detect_statistics_daily (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  stat_date          DATE NOT NULL,
  scenario           VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'all = 全场景',
  status             VARCHAR(16) NOT NULL DEFAULT 'all' COMMENT 'all = 全状态',
  total_count        INT NOT NULL DEFAULT 0 COMMENT '该分片任务数',
  done_count         INT NOT NULL DEFAULT 0,
  ai_rate_sum        DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'DONE 任务 ai_rate 之和',
  avg_ai_rate        DECIMAL(5,2) NULL COMMENT 'ai_rate_sum / done_count，写入时同步算',
  pass_count         INT NOT NULL DEFAULT 0 COMMENT '达标数（ai_rate ≤ threshold）',
  over_count         INT NOT NULL DEFAULT 0 COMMENT '超线数',
  source_labels_json JSON NULL COMMENT '溯源主标签计数 {gpt: 3, qwen: 1}',
  updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_scenario_status (stat_date, scenario, status),
  INDEX idx_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '检测数据按天×场景×状态物化统计';
