package com.paperaigc.detect.domain.dto;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 候选合并发布为 edu_school_rule（人工审核：字段在 UI 由候选预填、人工确认后提交）。
 * sourceUrl 必填——留痕原文地址。
 */
@Data
public class CandidateMergeDTO {
    private Long schoolId;          // 候选 schoolId 可能为空，人工认领
    private String college;         // 空=全校
    private String degreeType;      // bachelor/master/phd
    private BigDecimal aiRateLimit;
    private BigDecimal plagiarismLimit;
    private String platform;
    private Integer effectiveYear;
    private String sourceUrl;       // 必填
}
