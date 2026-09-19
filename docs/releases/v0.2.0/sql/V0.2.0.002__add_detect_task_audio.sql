-- ============================================================
-- V0.2.0.002 · detect_task 补音频列（Wave 5 · audio 模态支持）
-- 对齐 com.paperaigc.detect.domain.entity.DetectTask.audioSegments / audioDurationSec
-- 音频段级明细走 JSON 单列（数据量小 · 不需要按段查询），不建独立子表
-- ============================================================

ALTER TABLE detect_task
  ADD COLUMN modality             VARCHAR(16) NOT NULL DEFAULT 'text' COMMENT '模态：text / audio / image' AFTER user_id,
  ADD COLUMN audio_duration_sec   DECIMAL(8,2) NULL COMMENT '音频总时长（秒 · audio 模态）' AFTER excluded_paragraph_count,
  ADD COLUMN audio_segments_json  JSON NULL COMMENT '音频段级明细 · [{segmentIdx,timeStart,timeEnd,aiProb,calibratedProb,sourceLabel,waveformPeak}]' AFTER audio_duration_sec,
  ADD INDEX idx_modality_time (modality, created_at);
