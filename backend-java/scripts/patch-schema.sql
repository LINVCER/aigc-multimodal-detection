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
  paragraph_idxs JSON NULL COMMENT '申诉勾选的段落序号 [0,3,7]',
  consent_improve TINYINT(1) NOT NULL DEFAULT 0 COMMENT '用户同意勾选段落用于改进模型（仅评测）',
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
  parent_task_id            BIGINT NULL COMMENT '修改稿对应的上一次任务（复测关联）',
  modality                  VARCHAR(16) NOT NULL DEFAULT 'text' COMMENT '模态：text',
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
  INDEX idx_scenario_time  (scenario, created_at),
  INDEX idx_modality_time  (modality, created_at),
  INDEX idx_parent         (parent_task_id)
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

-- ==================== 论文检测助手 · 对话审计 ====================
-- 对齐 com.paperaigc.detect.domain.entity.AssistantLog · 误报分析 / 合规留存 / 改写请求占比统计
CREATE TABLE IF NOT EXISTS assistant_log (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id            BIGINT NULL,
  conversation_id    VARCHAR(32) NULL,
  task_id            BIGINT NULL,
  question           VARCHAR(500) NULL COMMENT '用户问题（截断）',
  answer             VARCHAR(1000) NULL COMMENT '助手回答（截断）',
  intent             VARCHAR(32) NULL COMMENT 'explain / policy / guide / appeal / rewrite_request / history / chitchat / other',
  tools              VARCHAR(255) NULL COMMENT '本轮调用的工具，逗号分隔',
  model              VARCHAR(64) NULL,
  prompt_tokens      INT NULL,
  completion_tokens  INT NULL,
  latency_ms         INT NULL,
  finish_reason      VARCHAR(32) NULL COMMENT 'stop / tool_calls / safety / error / tool_rounds_exceeded',
  safety             VARCHAR(16) NULL COMMENT 'pass / blocked / degraded',
  boundary_flag      TINYINT(1) NOT NULL DEFAULT 0 COMMENT '回答疑似越界（针对原文给成品改写），人工抽查',
  boundary_type      VARCHAR(32) NULL COMMENT '越界类型：rewrite / bypass / ghostwrite / appeal_fabricate',
  kb_top_score       DECIMAL(6,3) NULL COMMENT '知识库 top-1 BM25 分数，低于阈值视为知识缺口；NULL=本轮未检索',
  kb_top_ref         VARCHAR(160) NULL COMMENT '知识库 top-1 块引用 doc › title',
  error_code         VARCHAR(64) NULL,
  client_context     VARCHAR(500) NULL COMMENT '端 / 页面 / 版本 JSON',
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_time   (user_id, created_at),
  INDEX idx_conv        (conversation_id),
  INDEX idx_intent_time (intent, created_at),
  INDEX idx_boundary    (boundary_flag, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '助手对话审计';

-- ==================== 误判候选样本池（增长闭环 §2.2，只进评测） ====================
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

-- ==================== 助手对话质检标注（增长闭环 §3） ====================
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

-- ==================== 检测数据物化统计（detect-analytics-plan §3.2） ====================
CREATE TABLE IF NOT EXISTS detect_statistics_daily (
  id                 BIGINT PRIMARY KEY AUTO_INCREMENT,
  stat_date          DATE NOT NULL,
  scenario           VARCHAR(32) NOT NULL DEFAULT 'all' COMMENT 'all = 全场景',
  status             VARCHAR(16) NOT NULL DEFAULT 'all' COMMENT 'all = 全状态',
  total_count        INT NOT NULL DEFAULT 0,
  done_count         INT NOT NULL DEFAULT 0,
  ai_rate_sum        DECIMAL(12,2) NOT NULL DEFAULT 0 COMMENT 'DONE 任务 ai_rate 之和',
  avg_ai_rate        DECIMAL(5,2) NULL,
  pass_count         INT NOT NULL DEFAULT 0,
  over_count         INT NOT NULL DEFAULT 0,
  source_labels_json JSON NULL COMMENT '溯源主标签计数',
  updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_date_scenario_status (stat_date, scenario, status),
  INDEX idx_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '检测数据按天×场景×状态物化统计';

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

-- ==================== 论文检测助手 · 知识库分块 ====================
-- 对齐 deploy/inference-python/assistant/knowledge.py 的 Chunk 结构
-- 设计见 docs/design/202610-knowledge-base-retrieval-plan.md（Phase 1）
CREATE TABLE IF NOT EXISTS knowledge_chunk (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  doc          VARCHAR(64)  NOT NULL COMMENT '来源文档，如 07-verification',
  title        VARCHAR(128) NOT NULL COMMENT '块标题（## 二级标题）',
  tags         VARCHAR(255) DEFAULT '' COMMENT '文件级标签，逗号分隔',
  body         TEXT         NOT NULL COMMENT '块正文',
  sort_order   INT          NOT NULL DEFAULT 0 COMMENT '同文档内顺序',
  enabled      TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '运营可下线某块（0=下线不参与检索）',
  created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_doc_title (doc, title),
  INDEX idx_doc (doc),
  INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '助手知识库分块（运营可编辑，推理服务启动时全量加载进内存 BM25）';

-- ==================== 论文检测助手 · 会话（聊天记录持久化） ====================
-- 对齐 deploy/inference-python/assistant/session.py；保留 session_ttl_days（默认 7 天）
CREATE TABLE IF NOT EXISTS assistant_conversation (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  conversation_id  VARCHAR(32) NOT NULL,
  user_id          BIGINT NULL,
  task_id          BIGINT NULL,
  title            VARCHAR(128) DEFAULT '' COMMENT '首条用户消息前 30 字',
  messages_json    JSON NOT NULL COMMENT '会话消息数组 [{role,content,ts,...}]',
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_conv (conversation_id),
  INDEX idx_user_updated (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '助手会话（保留 session_ttl_days 天）';


