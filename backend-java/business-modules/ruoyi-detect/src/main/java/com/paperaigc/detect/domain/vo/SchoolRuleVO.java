package com.paperaigc.detect.domain.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/** 已发布红线项（公开查询页 / 详情用） */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SchoolRuleVO {
    private String degreeType;
    private String college;
    private BigDecimal aiRateLimit;
    private BigDecimal plagiarismLimit;
    private String platform;
    private Integer effectiveYear;
    private String sourceUrl;
}
