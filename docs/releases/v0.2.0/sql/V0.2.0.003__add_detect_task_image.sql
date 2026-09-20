-- ============================================================
-- V0.2.0.003 · detect_task 追加图像模态列
-- 对齐 docs/design/202609-image-backend-integration-plan.md §6
--
-- 幂等：INFORMATION_SCHEMA 存在性判定后 ALTER，可重复执行
-- ============================================================

SET @has_col := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME   = 'detect_task'
      AND COLUMN_NAME  = 'image_segments_json'
);

SET @sql := IF(@has_col = 0,
    'ALTER TABLE detect_task
       ADD COLUMN image_segments_json JSON NULL
       COMMENT ''图像区域级 · [{segmentIdx,x,y,w,h,aiProb,calibratedProb,sourceLabel}]''
       AFTER audio_segments_json',
    'SELECT ''column image_segments_json already exists, skip'' AS msg'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
