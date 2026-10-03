-- ============================================================
-- V0.3.0.001 · 论文检测助手对话审计表
-- 对齐 com.paperaigc.detect.domain.entity.AssistantLog
-- 设计见 docs/design/202610-paper-assistant-agent-research.md §3.9
-- 幂等：CREATE TABLE IF NOT EXISTS
-- ============================================================

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
  error_code         VARCHAR(64) NULL,
  client_context     VARCHAR(500) NULL COMMENT '端 / 页面 / 版本 JSON',
  created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_user_time   (user_id, created_at),
  INDEX idx_conv        (conversation_id),
  INDEX idx_intent_time (intent, created_at),
  INDEX idx_boundary    (boundary_flag, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '助手对话审计';
