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
 * 爬虫候选 = 审核队列 —— edu_school_rule_candidate（V0.3.0.014）
 *
 * <p>highschool-spider 产出的原始 per-metric 行，status=pending，必带 sourceUrl；
 * 后台人工核对后合并发布为 {@link EduSchoolRule}。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("edu_school_rule_candidate")
public class EduSchoolRuleCandidate {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long schoolId;
    private String schoolName;
    /** bachelor / master / phd / unknown */
    private String degreeType;
    /** ai_rate / plagiarism */
    private String metric;
    private BigDecimal limitPct;
    private String platform;
    private Integer effectiveYear;
    /** 原文片段，供人工核对 */
    private String snippet;
    /** 原文地址（非空） */
    private String sourceUrl;
    private Integer confidence;
    /** sha1 去重 */
    private String contentHash;
    /** pending / merged / rejected */
    private String status;
    private Long mergedRuleId;

    private LocalDateTime createdAt;
}
