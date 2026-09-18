package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 音频片段级检测结果
 *
 * <p>跟 ParagraphResult（文本段）对齐：都是 idx + aiProb + calibratedProb 三元组，
 * 音频独有 timeStart/timeEnd（秒）。前端渲染时按 modality 走不同视图。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class AudioSegmentResult {

    /** 片段序号（0 起） */
    private Integer segmentIdx;

    /** 时间戳（秒，浮点） */
    private Double timeStart;
    private Double timeEnd;

    /** 原始 AI 概率 */
    private Double aiProb;

    /** 校准后 AI 概率（前端展示与阈值判定用） */
    private Double calibratedProb;

    /** 疑似 AI 生成源（tts / cloned_voice / real_human 等；Wave 5 前保留 null） */
    private String sourceLabel;

    /** 波形能量峰值（0-1，前端画波形用；stub 阶段可为 null） */
    private Double waveformPeak;
}
