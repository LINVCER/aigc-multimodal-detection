-- ============================================================
-- R · 6 场景默认阈值（幂等 · 每次部署都跑；已存在则更新 label）
-- 对齐 docs/design/OPERATIONS_REQUIREMENTS.md §3.7
-- ============================================================

INSERT INTO detect_scenario_threshold (scenario, label, threshold, enabled) VALUES
  ('academic_bachelor', '学术·本科', 20.00, 1),
  ('academic_master',   '学术·硕士', 15.00, 1),
  ('academic_phd',      '学术·博士', 10.00, 1),
  ('job_report',        '职业报告',   15.00, 1),
  ('self_media',        '自媒体',     30.00, 1),
  ('other',             '其他',       25.00, 1)
ON DUPLICATE KEY UPDATE label = VALUES(label);
