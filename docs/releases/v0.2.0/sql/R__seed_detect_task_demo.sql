-- ============================================================
-- R · detect_task seed 样例（幂等 · 每次部署都跑）
-- 供开发/演示使用，生产环境部署前应清空
-- ============================================================

INSERT INTO detect_task (id, user_id, modality, paper_title, status, scenario, threshold, ai_rate, file_path, original_filename, file_size, model_version, word_count, body_paragraph_count, excluded_paragraph_count, source_labels_json, created_at, finished_at) VALUES

-- ==================== 文本检测 · 已完成 ====================
(1004, 10001, 'text', '基于Transformer的医疗影像报告自动生成研究', 'DONE', 'academic_master', 15, 18.70, 'uploads/2026/09/1004.docx', '医疗影像报告生成_v3.docx', 245760, 'v2.1.0', 10240, 22, 1, '{"qwen": 0.45, "gpt": 0.35, "other": 0.20}', NOW() - INTERVAL 7 DAY, NOW() - INTERVAL 7 DAY + INTERVAL 3 MINUTE),

(1005, 10001, 'text', '面向金融风控的知识图谱构建与应用', 'DONE', 'academic_master', 15, 12.30, 'uploads/2026/09/1005.docx', '金融风控知识图谱_终稿.docx', 312000, 'v2.1.0', 13500, 28, 2, '{"qwen": 0.30, "gpt": 0.25, "other": 0.45}', NOW() - INTERVAL 6 DAY, NOW() - INTERVAL 6 DAY + INTERVAL 5 MINUTE),

(1006, 10002, 'text', '智慧城市交通拥堵预测算法研究', 'DONE', 'academic_phd', 10, 5.40, 'uploads/2026/09/1006.docx', '交通预测算法_博士论文.docx', 189440, 'v2.1.0', 8200, 16, 0, '{"gpt": 0.10, "other": 0.90}', NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 5 DAY + INTERVAL 2 MINUTE),

(1007, 10002, 'text', '区块链技术在供应链溯源中的应用', 'DONE', 'academic_bachelor', 20, 35.80, 'uploads/2026/09/1007.docx', '区块链供应链_本科.docx', 156800, 'v2.0.3', 6800, 14, 3, '{"qwen": 0.55, "gpt": 0.30, "other": 0.15}', NOW() - INTERVAL 4 DAY, NOW() - INTERVAL 4 DAY + INTERVAL 4 MINUTE),

(1008, 10003, 'text', 'ChatGPT对高等教育影响的实证研究', 'DONE', 'academic_master', 15, 22.10, 'uploads/2026/09/1008.docx', 'ChatGPT高等教育研究.docx', 278500, 'v2.1.0', 11500, 24, 1, '{"qwen": 0.40, "gpt": 0.50, "other": 0.10}', NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY + INTERVAL 6 MINUTE),

(1009, 10003, 'text', '新能源汽车电池回收技术经济分析', 'DONE', 'job_report', 15, 9.60, 'uploads/2026/09/1009.docx', '电池回收技术经济分析.pdf', 421000, 'v2.1.0', 15800, 32, 0, '{"gpt": 0.15, "other": 0.85}', NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY + INTERVAL 3 MINUTE),

(1010, 10003, 'text', 'AI生成内容对自媒体行业的影响与机遇', 'DONE', 'self_media', 30, 62.50, 'uploads/2026/09/1010.docx', 'AI自媒体影响.docx', 98000, 'v2.0.3', 4200, 9, 0, '{"qwen": 0.70, "gpt": 0.25, "other": 0.05}', NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY + INTERVAL 1 MINUTE),

-- ==================== 文本检测 · 运行中 ====================
(1011, 10001, 'text', '基于大语言模型的代码自动修复技术研究', 'RUNNING', 'academic_phd', 10, NULL, 'uploads/2026/09/1011.docx', '代码自动修复_博士.docx', 356400, 'v2.1.0', 18200, 36, NULL, NULL, NOW() - INTERVAL 2 HOUR, NULL),

(1012, 10005, 'text', '元宇宙概念下虚拟数字人交互设计研究', 'RUNNING', 'academic_master', 15, NULL, 'uploads/2026/09/1012.docx', '元宇宙数字人设计.docx', 201000, 'v2.1.0', 9200, 19, NULL, NULL, NOW() - INTERVAL 1 HOUR, NULL),

(1013, 10003, 'text', '量子机器学习在药物发现中的应用综述', 'RUNNING', 'academic_phd', 10, NULL, 'uploads/2026/09/1013.docx', '量子机器学习药物发现.docx', 289000, 'v2.1.0', 14200, 28, NULL, NULL, NOW() - INTERVAL 30 MINUTE, NULL),

-- ==================== 文本检测 · 等待中 ====================
(1014, 10002, 'text', '联邦学习在医疗数据隐私保护中的应用', 'PENDING', 'academic_master', 15, NULL, 'uploads/2026/09/1014.docx', '联邦学习医疗隐私.docx', 234500, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 10 MINUTE, NULL),

(1015, 10001, 'text', '基于深度强化学习的智能电网调度优化', 'PENDING', 'academic_bachelor', 20, NULL, 'uploads/2026/09/1015.docx', '智能电网调度优化_初稿.docx', 178000, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 5 MINUTE, NULL),

(1016, 10005, 'text', '短视频平台推荐算法对青少年心理健康影响研究', 'PENDING', 'other', 25, NULL, 'uploads/2026/09/1016.docx', '短视频青少年心理.docx', 112000, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 1 MINUTE, NULL),

-- ==================== 文本检测 · 失败 ====================
(1017, 10001, 'text', '基于图神经网络的社交网络异常检测', 'FAILED', 'academic_master', 15, NULL, 'uploads/2026/09/1017.docx', '图神经网络异常检测.docx', 198000, 'v2.1.0', NULL, NULL, NULL, NULL, NOW() - INTERVAL 1 DAY, NOW() - INTERVAL 1 DAY + INTERVAL 2 MINUTE),

-- ==================== 音频检测 ====================
(1018, 10003, 'audio', '2026年秋季学期开学典礼校长致辞', 'DONE', 'other', 25, 11.20, 'uploads/2026/09/1018.wav', '开学典礼致辞_录音.wav', 18432000, 'v2.1.0', NULL, NULL, NULL, '{"qwen": 0.20, "gpt": 0.15, "other": 0.65}', NOW() - INTERVAL 3 DAY, NOW() - INTERVAL 3 DAY + INTERVAL 8 MINUTE),

(1019, 10002, 'audio', '新媒体运营月度复盘会议录音', 'DONE', 'self_media', 30, 28.60, 'uploads/2026/09/1019.mp3', '月度复盘会议_202608.mp3', 25600000, 'v2.1.0', NULL, NULL, NULL, '{"qwen": 0.35, "gpt": 0.20, "other": 0.45}', NOW() - INTERVAL 2 DAY, NOW() - INTERVAL 2 DAY + INTERVAL 12 MINUTE),

(1020, 10005, 'audio', '产品需求评审会议录音_20260915', 'RUNNING', 'job_report', 15, NULL, 'uploads/2026/09/1020.m4a', '产品需求评审_0915.m4a', 31200000, 'v2.1.0', NULL, NULL, NULL, NULL, NOW() - INTERVAL 3 HOUR, NULL),

(1021, 10001, 'audio', '在线课程试讲视频音轨_数据结构', 'PENDING', 'academic_bachelor', 20, NULL, 'uploads/2026/09/1021.wav', '数据结构试讲_音轨.wav', 45600000, NULL, NULL, NULL, NULL, NULL, NOW() - INTERVAL 20 MINUTE, NULL)

ON DUPLICATE KEY UPDATE
  paper_title  = VALUES(paper_title),
  status       = VALUES(status),
  ai_rate      = VALUES(ai_rate),
  word_count   = VALUES(word_count),
  finished_at  = VALUES(finished_at);