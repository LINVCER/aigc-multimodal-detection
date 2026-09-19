-- ============================================================
-- V0.2.0.001 · C 端用户档案表 user_profile
-- 对齐 com.paperaigc.detect.domain.entity.AdminUser（Phase B · Batch 2）
-- 跟若依 sys_user 严格分离：sys_user = 后台运营账号，user_profile = C 端用户
-- ============================================================

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
