-- ============================================================
-- V0.3.0.007 · 对话质检标注表 + 复测关联（增长闭环 §3 / §5）
-- 幂等
-- ============================================================

-- 运营抽样质检：每条标注指向一个会话（可选到具体一轮 log）
CREATE TABLE IF NOT EXISTS assistant_quality_note (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  conversation_id  VARCHAR(32) NOT NULL,
  log_id           BIGINT NULL COMMENT '具体哪一轮 assistant_log.id，空=整段会话',
  score            TINYINT NULL COMMENT '1-5',
  tag              VARCHAR(32) NOT NULL COMMENT 'good / wrong_fact / off_point / boundary / tone',
  note             VARCHAR(500) NULL,
  reviewer         BIGINT NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_conv (conversation_id),
  INDEX idx_tag_time (tag, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '助手对话质检标注';

-- 复测关联：修改稿指向上一次任务，报告页显示「比上次 −X%」
SET @c1 := (SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND COLUMN_NAME = 'parent_task_id');
SET @sql := IF(@c1 = 0,
  'ALTER TABLE detect_task ADD COLUMN parent_task_id BIGINT NULL COMMENT ''修改稿对应的上一次任务'' AFTER user_id',
  'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @i1 := (SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'detect_task' AND INDEX_NAME = 'idx_parent');
SET @sql := IF(@i1 = 0, 'ALTER TABLE detect_task ADD INDEX idx_parent (parent_task_id)', 'SELECT 1');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
