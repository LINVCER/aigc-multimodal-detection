-- ============================================================
-- V0.3.0.005 · assistant_log 增加知识命中分数 / 引用（增长闭环 §1.1 知识缺口信号）
-- 对齐 com.paperaigc.detect.domain.entity.AssistantLog.kbTopScore / kbTopRef
-- 幂等：列存在则跳过
-- ============================================================

SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'assistant_log' AND COLUMN_NAME = 'kb_top_score');
SET @sql := IF(@c1 = 0,
  'ALTER TABLE assistant_log ADD COLUMN kb_top_score DECIMAL(6,3) NULL COMMENT ''知识库 top-1 BM25 分数，低于阈值视为知识缺口；NULL=本轮未检索'' AFTER boundary_type',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @c2 := (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'assistant_log' AND COLUMN_NAME = 'kb_top_ref');
SET @sql := IF(@c2 = 0,
  'ALTER TABLE assistant_log ADD COLUMN kb_top_ref VARCHAR(160) NULL COMMENT ''知识库 top-1 块引用 doc › title'' AFTER kb_top_score',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 缺口查询用：意图 + 分数
SET @i1 := (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'assistant_log' AND INDEX_NAME = 'idx_intent_kb');
SET @sql := IF(@i1 = 0, 'ALTER TABLE assistant_log ADD INDEX idx_intent_kb (intent, kb_top_score, created_at)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
