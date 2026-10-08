-- ============================================================
-- V0.3.0.012 · detect_task 增加报告溯源凭证列
-- 对齐 com.paperaigc.detect.domain.entity.DetectTask.reportNo / verifyCode / reportSign / signedAt / verifyCount
-- 幂等：用 information_schema 检查列是否存在，已存在则跳过
-- ============================================================

SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'report_no');
SET @sql := IF(@c1 = 0, 'ALTER TABLE detect_task ADD COLUMN report_no VARCHAR(32) NULL COMMENT ''报告编号 ZY-yyyyMMdd-XXXXXX'' AFTER finished_at', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c2 := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'verify_code');
SET @sql := IF(@c2 = 0, 'ALTER TABLE detect_task ADD COLUMN verify_code VARCHAR(16) NULL COMMENT ''验证码 8 位'' AFTER report_no', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c3 := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'report_sign');
SET @sql := IF(@c3 = 0, 'ALTER TABLE detect_task ADD COLUMN report_sign VARCHAR(64) NULL COMMENT ''HMAC-SHA256 签名 hex'' AFTER verify_code', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c4 := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'signed_at');
SET @sql := IF(@c4 = 0, 'ALTER TABLE detect_task ADD COLUMN signed_at DATETIME NULL COMMENT ''签发时间'' AFTER report_sign', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c5 := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'verify_count');
SET @sql := IF(@c5 = 0, 'ALTER TABLE detect_task ADD COLUMN verify_count INT NOT NULL DEFAULT 0 COMMENT ''被验证次数'' AFTER signed_at', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @i1 := (SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND INDEX_NAME = 'uk_report_no');
SET @sql := IF(@i1 = 0, 'ALTER TABLE detect_task ADD UNIQUE INDEX uk_report_no (report_no)', 'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
