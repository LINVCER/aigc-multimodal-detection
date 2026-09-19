-- ============================================================
-- ⚠ 此文件是「当前累计的全量 schema 快照」，仅用于本地一键搭数据库
-- 规范化的版本化迁移见 docs/releases/{version}/sql/（Flyway V*/R* 命名）
-- 未来所有增量走那里，本文件只在发版时同步全量快照，不再单点追加
-- ============================================================

-- W3.a baseline · 业务补表（对齐 docs/design/OPERATIONS_REQUIREMENTS.md §5）
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

-- ==================== C 端用户档案（Phase B · Batch 2）====================
-- 对齐 com.paperaigc.detect.domain.entity.AdminUser · 跟若依 sys_user 严格分离
CREATE TABLE IF NOT EXISTS user_profile (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  login_type    VARCHAR(16) NOT NULL COMMENT '登录方式：phone / wechat / email',
  identity      VARCHAR(128) NOT NULL COMMENT '脱敏账号：138****5678 / abc****@163.com / oGvz1w****',
  detect_count  INT NOT NULL DEFAULT 0 COMMENT '累计检测数缓存（CronJob 或 CDC 从 detect_task 聚合刷新）',
  last_login_at DATETIME NULL,
  registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  status        VARCHAR(16) NOT NULL DEFAULT 'NORMAL' COMMENT 'NORMAL / BANNED / INACTIVE / SUSPICIOUS',
  INDEX idx_login_type      (login_type),
  INDEX idx_status_reg_time (status, registered_at),
  INDEX idx_registered_at   (registered_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT 'C 端用户档案';

-- ==================== 检测任务 ====================
-- 对齐 com.paperaigc.detect.domain.entity.DetectTask（Phase B 切 MyBatis-Plus 时 @TableName 指此表）
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
  INDEX idx_user_time      (user_id, created_at),
  INDEX idx_status_time    (status,  created_at),
  INDEX idx_scenario_time  (scenario, created_at)
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
