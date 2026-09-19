-- ============================================================
-- R · user_profile 6 条 seed 样例（幂等 · 每次部署都跑）
-- 从 InMemoryAdminUserRepository.@PostConstruct 迁移
-- 生产环境 seed 前应先 TRUNCATE user_profile；本 seed 主要供开发/演示用
-- ============================================================

INSERT INTO user_profile (id, login_type, identity, detect_count, last_login_at, registered_at, status) VALUES
  (10001, 'phone',  '138****5678',      12,  NOW() - INTERVAL 3 MINUTE,   NOW() - INTERVAL 45 DAY,  'NORMAL'),
  (10002, 'wechat', 'oGvz1w****',        3,  NOW() - INTERVAL 2 HOUR,     NOW() - INTERVAL 30 DAY,  'NORMAL'),
  (10003, 'email',  'abc****@163.com',  47,  NOW() - INTERVAL 20 MINUTE,  NOW() - INTERVAL 90 DAY,  'NORMAL'),
  (10004, 'phone',  '139****0011',       0,  NOW() - INTERVAL 60 DAY,     NOW() - INTERVAL 60 DAY,  'INACTIVE'),
  (10005, 'phone',  '180****9999',     250,  NOW() - INTERVAL 1 MINUTE,   NOW() - INTERVAL 120 DAY, 'SUSPICIOUS'),
  (10006, 'email',  'test****@qq.com',   8,  NOW() - INTERVAL 3 DAY,      NOW() - INTERVAL 20 DAY,  'BANNED')
ON DUPLICATE KEY UPDATE
  login_type    = VALUES(login_type),
  identity      = VALUES(identity),
  detect_count  = VALUES(detect_count),
  status        = VALUES(status);
