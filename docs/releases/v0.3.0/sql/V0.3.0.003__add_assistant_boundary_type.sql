-- ============================================================
-- V0.3.0.003 · assistant_log 增加越界类型列
-- 对齐 com.paperaigc.detect.domain.entity.AssistantLog.boundaryType
-- 幂等：用 information_schema 检查列是否存在，已存在则跳过
-- 背景：agent 边界从单一 boundary_flag 升级为类型化（rewrite/bypass/ghostwrite/appeal_fabricate）
-- ============================================================

SET @col_exists := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'assistant_log'
    AND COLUMN_NAME = 'boundary_type'
);

SET @sql := IF(
  @col_exists = 0,
  'ALTER TABLE assistant_log ADD COLUMN boundary_type VARCHAR(32) NULL COMMENT ''越界类型：rewrite / bypass / ghostwrite / appeal_fabricate'' AFTER boundary_flag',
  'SELECT 1'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
