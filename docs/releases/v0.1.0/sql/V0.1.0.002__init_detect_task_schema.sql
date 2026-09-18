-- ============================================================
-- V0.1.0.002 · 检测任务主线表（对齐 com.paperaigc.detect.domain.entity.*）
-- Phase B 切 MyBatis-Plus 时 @TableName 直接指此表
-- ============================================================

-- ==================== 检测任务 ====================
CREATE TABLE IF NOT EXISTS detect_task (
  id                        BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id                   BIGINT NULL COMMENT 'Sa-Token 接入后填 sys_user.user_id',
  paper_title               VARCHAR(255) NOT NULL,
  status                    VARCHAR(16) NOT NULL COMMENT 'PENDING / RUNNING / DONE / FAILED',
  scenario                  VARCHAR(32) NOT NULL COMMENT '场景码 academic_bachelor 等',
  threshold                 INT NOT NULL COMMENT 'AI 率红线快照，避免运营改配置后历史任务变红线',
  ai_rate                   DECIMAL(5,2) NULL,
  file_path                 VARCHAR(512) NULL COMMENT 'IStorageService 生成的相对路径',
  original_filename         VARCHAR(255) NULL,
  file_size                 BIGINT NULL,
  model_version             VARCHAR(64) NULL,
  word_count                INT NULL,
  body_paragraph_count      BIGINT NULL,
  excluded_paragraph_count  INT NULL,
  source_labels_json        JSON NULL COMMENT '溯源分布 { qwen:0.4, gpt:0.3, ... }',
  created_at                DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at               DATETIME NULL,
  INDEX idx_user_time     (user_id, created_at),
  INDEX idx_status_time   (status,  created_at),
  INDEX idx_scenario_time (scenario, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '检测任务';

-- ==================== 段级结果 ====================
CREATE TABLE IF NOT EXISTS detect_paragraph_result (
  id                    BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id               BIGINT NOT NULL,
  paragraph_idx         INT NOT NULL,
  text                  TEXT NOT NULL,
  excluded              TINYINT(1) NOT NULL DEFAULT 0,
  exclude_reason        VARCHAR(32) NULL COMMENT 'reference / acknowledgement / appendix / sectionTitle / caption',
  ai_prob               DECIMAL(6,4) NULL,
  calibrated_prob       DECIMAL(6,4) NULL,
  confidence_interval   JSON NULL,
  source_label          VARCHAR(32) NULL,
  section_name          VARCHAR(64) NULL,
  warnings_json         JSON NULL,
  UNIQUE KEY uk_task_para (task_id, paragraph_idx),
  INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '段级检测结果';

-- ==================== 句级结果 ====================
CREATE TABLE IF NOT EXISTS detect_sentence_result (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_id        BIGINT NOT NULL,
  paragraph_idx  INT NOT NULL,
  sentence_idx   INT NOT NULL,
  text           TEXT NOT NULL,
  ai_prob        DECIMAL(6,4) NULL,
  UNIQUE KEY uk_task_para_sent (task_id, paragraph_idx, sentence_idx),
  INDEX idx_task_para (task_id, paragraph_idx)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '句级检测结果';
