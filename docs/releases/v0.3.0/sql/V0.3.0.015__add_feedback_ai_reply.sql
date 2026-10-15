-- ============================================================
-- V0.3.0.015 · 用户反馈 AI 自动回复（人工审核）
-- 用户提交反馈后自动生成 AI 回复草稿，管理员审核/编辑后才作为正式回复发出。
-- 草稿只存 ai_reply，不进 handled_reply；用户端展示逻辑不变。
-- 幂等：information_schema 检查后增列。
-- ============================================================

SET @db = DATABASE();

SET @sql = (SELECT IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'user_feedback' AND COLUMN_NAME = 'ai_reply') = 0,
  'ALTER TABLE user_feedback ADD COLUMN ai_reply TEXT NULL COMMENT ''AI 生成的回复草稿（仅供管理员参考，审核前不对外）'' AFTER handled_at',
  'SELECT 1'));
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @sql = (SELECT IF(
  (SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'user_feedback' AND COLUMN_NAME = 'ai_reply_at') = 0,
  'ALTER TABLE user_feedback ADD COLUMN ai_reply_at DATETIME NULL COMMENT ''AI 草稿生成时间'' AFTER ai_reply',
  'SELECT 1'));
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
