package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

/**
 * 高校学位论文红线（已发布）—— edu_school_rule（V0.3.0.014）
 *
 * <p>一行 = 一个「学校 + 学院 + 学位」的红线；college 为空表示全校。
 * 必带 sourceUrl 原文地址（本轮决策：一律人工审核、留痕）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("edu_school_rule")
public class EduSchoolRule {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long schoolId;
    /** 学院，null = 全校 */
    private String college;
    /** bachelor / master / phd */
    private String degreeType;
    /** AIGC 率红线 % */
    private BigDecimal aiRateLimit;
    /** 查重率红线 % */
    private BigDecimal plagiarismLimit;
    /** cnki / vip / wanfang / gezida / other */
    private String platform;
    /** official / user / inferred */
    private String sourceType;
    /** 原文地址 */
    private String sourceUrl;
    private Integer effectiveYear;
    private Integer confidence;
    /** published / stale / rejected */
    private String status;
    private Long verifiedBy;
    private LocalDateTime verifiedAt;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
