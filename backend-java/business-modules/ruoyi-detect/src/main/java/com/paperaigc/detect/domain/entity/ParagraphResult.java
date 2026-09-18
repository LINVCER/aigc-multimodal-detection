package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 段落级检测结果
 *
 * <p>对齐 patch-schema.sql · detect_paragraph_result 表（Phase B 落库）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ParagraphResult {

    /** 段序号（0 起） */
    private Integer paragraphIdx;
    /** 原文 */
    private String text;
    /** 是否被排除在 AI 率计算之外（参考文献/图表/章节标题等） */
    private boolean excluded;
    /** 排除理由 reference / acknowledgement / appendix / sectionTitle / caption */
    private String excludeReason;
    /** 原始 AI 概率（未校准） */
    private Double aiProb;
    /** 校准后 AI 概率（前端展示与阈值判定用） */
    private Double calibratedProb;
    /** 置信区间 [lower, upper]；Python 侧返回结构 */
    private Object confidenceInterval;
    /** 疑似 AI 来源标签 gpt / claude / qwen / deepseek / human 等 */
    private String sourceLabel;
    /** 段所在章节名（正文 / 摘要 / 引言 / …） */
    private String sectionName;
    /** 段落级警告（如 tokens 超上限截断等） */
    private List<String> warnings;
    /** 句级明细 */
    private List<SentenceResult> sentences;
}
