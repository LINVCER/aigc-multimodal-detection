-- ============================================================
-- V0.3.0.009 · 平台账号表 auth_user（登录/注册 · 密码 BCrypt hash）
-- 对齐 com.paperaigc.detect.domain.entity.UserAccount
-- 幂等：表存在则跳过
-- ============================================================

CREATE TABLE IF NOT EXISTS auth_user (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  username      VARCHAR(64)  NOT NULL COMMENT '登录名（学号/工号/邮箱）',
  password_hash VARCHAR(128) NOT NULL COMMENT 'BCrypt hash',
  real_name     VARCHAR(64)  NULL COMMENT '真实姓名/昵称',
  role          VARCHAR(32)  NOT NULL DEFAULT 'USER' COMMENT 'USER / ADMIN / OPS_ADMIN',
  org_name      VARCHAR(128) NULL COMMENT '组织/学校（可选）',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '平台账号';

-- 预置管理员：admin / admin123（BCrypt hash 见 AuthServiceImpl 启动时兜底，也可由注册产生）
