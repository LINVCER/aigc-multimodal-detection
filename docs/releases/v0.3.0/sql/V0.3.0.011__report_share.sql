-- ============================================================
-- V0.3.0.011 · 报告只读分享链接 report_share
-- 对齐 com.paperaigc.detect.domain.entity.ReportShare
-- 幂等：表存在则跳过
-- ============================================================

CREATE TABLE IF NOT EXISTS report_share (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  token          VARCHAR(64)  NOT NULL COMMENT '32 位随机串，公开页 /s/{token}',
  task_id        BIGINT       NOT NULL COMMENT 'detect_task.id',
  owner_user_id  BIGINT       NULL COMMENT '创建者',
  watermark      VARCHAR(40)  NULL COMMENT '页面水印文字',
  expires_at     DATETIME     NOT NULL COMMENT '到期时间',
  view_count     INT          NOT NULL DEFAULT 0,
  revoked        TINYINT      NOT NULL DEFAULT 0 COMMENT '1 已撤销',
  last_viewed_at DATETIME     NULL,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_token (token),
  KEY idx_task (task_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '报告只读分享链接';
