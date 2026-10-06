-- ============================================================
-- V0.3.0.006 · 申诉到段级 + 误判样本池（增长闭环 §2.2）
-- 对齐 Feedback.paragraphIdxs / consentImprove · HardSample
-- 幂等：列 / 表存在则跳过
-- ============================================================

SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_feedback' AND COLUMN_NAME = 'paragraph_idxs');
SET @sql := IF(@c1 = 0,
  'ALTER TABLE user_feedback ADD COLUMN paragraph_idxs JSON NULL COMMENT ''申诉勾选的段落序号 [0,3,7]'' AFTER task_id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @c2 := (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'user_feedback' AND COLUMN_NAME = 'consent_improve');
SET @sql := IF(@c2 = 0,
  'ALTER TABLE user_feedback ADD COLUMN consent_improve TINYINT(1) NOT NULL DEFAULT 0 COMMENT ''用户同意勾选段落用于改进模型（仅评测）'' AFTER paragraph_idxs',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 误判样本池：申诉 / 助手 create_appeal / 运营手动 三个来源；只进评测集，不进训练（方案 §2.1）
CREATE TABLE IF NOT EXISTS detect_hard_sample (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  feedback_id    BIGINT NULL COMMENT '来源申诉 user_feedback.id',
  task_id        BIGINT NOT NULL,
  paragraph_idx  INT NOT NULL,
  text_sha256    CHAR(64) NOT NULL COMMENT '段落文本哈希；未授权时只存这个',
  text           TEXT NULL COMMENT '仅 consent_improve=1 时快照，否则 NULL',
  model_prob     DECIMAL(6,4) NULL COMMENT '当时的 calibratedProb',
  model_version  VARCHAR(64) NOT NULL DEFAULT 'unknown',
  user_label     VARCHAR(16) NOT NULL DEFAULT 'human' COMMENT '用户主张：human / ai / mixed',
  ops_verdict    VARCHAR(16) NULL COMMENT '运营复核：confirm_fp / confirm_tp / unsure',
  source         VARCHAR(16) NOT NULL DEFAULT 'appeal' COMMENT 'appeal / assistant / ops',
  scenario       VARCHAR(32) NULL,
  reviewed_by    BIGINT NULL,
  reviewed_at    DATETIME NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_hash_version (text_sha256, model_version),
  INDEX idx_feedback (feedback_id),
  INDEX idx_task (task_id),
  INDEX idx_verdict_time (ops_verdict, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '误判候选样本池（评测用）';
