-- ============================================================
-- V0.3.0.004 · 论文检测助手会话表（聊天记录持久化）
-- 对齐 deploy/inference-python/assistant/session.py 的会话结构
-- 幂等：CREATE TABLE IF NOT EXISTS
-- 保留策略：session_ttl_days（默认 7 天），列表只返回 updated_at 在 N 天内的会话
-- ============================================================

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
