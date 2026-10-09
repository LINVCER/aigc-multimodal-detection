-- ============================================================
-- V0.3.0.013 · detect_task 增加失败原因列（异步推理失败兜底）
-- 对齐 com.paperaigc.detect.domain.entity.DetectTask.failReason
-- 幂等：用 information_schema 检查列是否存在，已存在则跳过
-- ============================================================

SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'fail_reason');
SET @sql := IF(@c1 = 0, 'ALTER TABLE detect_task ADD COLUMN fail_reason VARCHAR(512) NULL COMMENT ''失败原因（异步推理失败兜底）'' AFTER finished_at', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;