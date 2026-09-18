package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 句子级检测结果
 *
 * <p>对齐 patch-schema.sql · detect_sentence_result 表（Phase B 落库）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SentenceResult {
    /** 段内句序号（0 起） */
    private Integer sentenceIdx;
    /** 句子文本 */
    private String text;
    /** 句级 AI 概率 0-1 */
    private Double aiProb;
}
