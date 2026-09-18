-- W3.a · 业务补表（对齐 docs/design/OPERATIONS_REQUIREMENTS.md §5）
-- 前置：已导入若依 sys_* 全套（RuoYi-Vue-Plus/script/sql/ry_vue_5.X.sql）
-- 字符集：utf8mb4 / utf8mb4_0900_ai_ci

-- ==================== 用户反馈 ====================
CREATE TABLE IF NOT EXISTS user_feedback (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id       BIGINT NOT NULL,
  category      VARCHAR(16) NOT NULL COMMENT 'bug / suggestion / appeal',
  task_id       BIGINT NULL COMMENT '结果申诉时关联的检测任务 ID',
  content       TEXT NOT NULL,
  contact       VARCHAR(128) NULL,
  status        VARCHAR(16) NOT NULL DEFAULT 'PENDING' COMMENT 'PENDING/PROCESSING/REPLIED/IGNORED',
  handled_by    BIGINT NULL COMMENT '处理的运营账号 ID',
  handled_reply TEXT NULL,
  handled_at    DATETIME NULL,
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user (user_id),
  INDEX idx_status_time (status, created_at),
  INDEX idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT 'C 端反馈';

-- ==================== 场景预设阈值 ====================
CREATE TABLE IF NOT EXISTS detect_scenario_threshold (
  scenario   VARCHAR(32) PRIMARY KEY COMMENT 'academic_bachelor / academic_master / academic_phd / job_report / self_media / other',
  label      VARCHAR(64) NOT NULL COMMENT '展示名',
  threshold  DECIMAL(5,2) NOT NULL,
  enabled    TINYINT(1) NOT NULL DEFAULT 1,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '场景阈值配置';

INSERT INTO detect_scenario_threshold (scenario, label, threshold, enabled) VALUES
  ('academic_bachelor', '学术·本科', 20.00, 1),
  ('academic_master',   '学术·硕士', 15.00, 1),
  ('academic_phd',      '学术·博士', 10.00, 1),
  ('job_report',        '职业报告',   15.00, 1),
  ('self_media',        '自媒体',     30.00, 1),
  ('other',             '其他',       25.00, 1)
ON DUPLICATE KEY UPDATE label = VALUES(label);

-- ==================== 模型版本 ====================
CREATE TABLE IF NOT EXISTS model_version (
  id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
  version_code        VARCHAR(64) NOT NULL UNIQUE,
  backbone            VARCHAR(64),
  train_dataset       VARCHAR(255),
  val_f1              DECIMAL(6,4),
  ece                 DECIMAL(6,4),
  calibration_params  JSON,
  status              VARCHAR(16) NOT NULL DEFAULT 'STAGING' COMMENT 'STAGING/PROD/RETIRED',
  rollout_pct         INT NOT NULL DEFAULT 0 COMMENT '灰度百分比 0-100（Phase 2 用）',
  storage_url         VARCHAR(512),
  created_by          BIGINT,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deployed_at         DATETIME NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '模型版本';

-- ==================== 异常账号标记 ====================
CREATE TABLE IF NOT EXISTS user_abnormal_flag (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id    BIGINT NOT NULL,
  flag_type  VARCHAR(32) NOT NULL COMMENT 'high_freq / bulk_ip / large_file / manual',
  detail     TEXT NULL COMMENT 'JSON 明细',
  handled    TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user (user_id),
  INDEX idx_handled_time (handled, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '异常账号';
