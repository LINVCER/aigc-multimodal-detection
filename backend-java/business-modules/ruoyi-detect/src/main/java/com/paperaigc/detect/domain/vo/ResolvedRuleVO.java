package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 当前用户生效的红线（上传页卡片 / 报告页文案 / 小白上下文）。
 * resolved=false 表示未命中学校规则，走通用口径兜底，label=「通用标准」。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResolvedRuleVO {
    private boolean resolved;
    private Long schoolId;
    private String schoolName;
    private String degreeType;
    private BigDecimal aiRateLimit;
    private BigDecimal plagiarismLimit;
    private String platform;
    private Integer effectiveYear;
    private String sourceUrl;
    private String sourceType;
    /** 展示标签，如「北航 · 硕士」/「通用标准」 */
    private String label;
}
