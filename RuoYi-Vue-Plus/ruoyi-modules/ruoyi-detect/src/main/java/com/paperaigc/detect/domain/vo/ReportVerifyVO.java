package com.paperaigc.detect.domain.vo;

import com.paperaigc.detect.domain.entity.DetectTask;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 公开验证结果：只给核对报告真伪需要的摘要字段，不含段落原文、用户、文件
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ReportVerifyVO {
    /** 编号与验证码匹配 */
    private boolean valid;
    /** 签名重算一致（valid=false 时为 false） */
    private boolean signatureValid;
    private String message;

    private String reportNo;
    private String paperTitle;
    private String scenario;
    private Integer threshold;
    private Double aiRate;
    private Boolean pass;
    private String modelVersion;
    private Integer wordCount;
    private Long bodyParagraphCount;
    private LocalDateTime detectedAt;
    private LocalDateTime signedAt;
    /** 签名前 16 位，与 PDF 上印的指纹比对 */
    private String fingerprint;
    private Integer verifyCount;

    public static ReportVerifyVO invalid(String message) {
        return ReportVerifyVO.builder().valid(false).signatureValid(false).message(message).build();
    }

    public static ReportVerifyVO of(DetectTask t, boolean signatureValid, String fingerprint, int verifyCount) {
        boolean pass = t.getAiRate() != null && t.getThreshold() != null && t.getAiRate() <= t.getThreshold();
        return ReportVerifyVO.builder()
                .valid(true)
                .signatureValid(signatureValid)
                .message(signatureValid ? "报告由知源签发，内容与签发时一致" : "编号有效，但报告内容与签发时不一致，可能被修改过")
                .reportNo(t.getReportNo())
                .paperTitle(t.getPaperTitle())
                .scenario(t.getScenario())
                .threshold(t.getThreshold())
                .aiRate(t.getAiRate())
                .pass(pass)
                .modelVersion(t.getModelVersion())
                .wordCount(t.getWordCount())
                .bodyParagraphCount(t.getBodyParagraphCount())
                .detectedAt(t.getFinishedAt() != null ? t.getFinishedAt() : t.getCreatedAt())
                .signedAt(t.getSignedAt())
                .fingerprint(fingerprint)
                .verifyCount(verifyCount)
                .build();
    }
}
