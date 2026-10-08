-- ============================================================
-- V0.3.0.010 · auth_user 增加账号状态与最近登录时间
-- 对齐 com.paperaigc.detect.domain.entity.UserAccount.status / lastLoginAt
-- 幂等：用 information_schema 检查列是否存在，已存在则跳过
-- ============================================================

SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auth_user' AND COLUMN_NAME = 'status');
SET @sql := IF(@c1 = 0,
  'ALTER TABLE auth_user ADD COLUMN status TINYINT NOT NULL DEFAULT 1 COMMENT ''1 正常 / 0 停用（停用后拒绝登录）'' AFTER org_name',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @c2 := (SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'auth_user' AND COLUMN_NAME = 'last_login_at');
SET @sql := IF(@c2 = 0,
  'ALTER TABLE auth_user ADD COLUMN last_login_at DATETIME NULL COMMENT ''最近一次登录成功时间'' AFTER status',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
