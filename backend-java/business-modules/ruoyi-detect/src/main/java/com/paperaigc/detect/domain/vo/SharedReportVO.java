package com.paperaigc.detect.domain.vo;

import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import com.paperaigc.detect.domain.entity.ReportShare;
import com.paperaigc.detect.domain.entity.SentenceResult;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 公开只读报告：不带任务 id / 用户 id / 文件信息，只给看报告需要的字段
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SharedReportVO {
    private String paperTitle;
    private String scenario;
    private Integer threshold;
    private Double aiRate;
    private String modelVersion;
    private Integer wordCount;
    private Long bodyParagraphCount;
    private Integer excludedParagraphCount;
    private LocalDateTime detectedAt;
    private Map<String, Double> sourceLabels;
    private List<Paragraph> paragraphs;

    private String reportNo;
    private String watermark;
    private LocalDateTime expiresAt;
    private Integer viewCount;

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Paragraph {
        private Integer paragraphIdx;
        private String text;
        private Boolean excluded;
        private String excludeReason;
        private Double calibratedProb;
        private String sourceLabel;
        private String sectionName;
        private List<Sentence> sentences;
    }

    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class Sentence {
        private Integer sentenceIdx;
        private String text;
        private Double aiProb;
    }

    public static SharedReportVO from(DetectTask t, ReportShare s, String defaultWatermark) {
        List<Paragraph> paras = t.getParagraphs() == null ? List.of() : t.getParagraphs().stream().map(SharedReportVO::para).toList();
        return SharedReportVO.builder()
                .paperTitle(t.getPaperTitle())
                .scenario(t.getScenario())
                .threshold(t.getThreshold())
                .aiRate(t.getAiRate())
                .modelVersion(t.getModelVersion())
                .wordCount(t.getWordCount())
                .bodyParagraphCount(t.getBodyParagraphCount())
                .excludedParagraphCount(t.getExcludedParagraphCount())
                .detectedAt(t.getFinishedAt() != null ? t.getFinishedAt() : t.getCreatedAt())
                .sourceLabels(t.getSourceLabels())
                .paragraphs(paras)
                .reportNo(t.getReportNo())
                .watermark(s.getWatermark() == null || s.getWatermark().isBlank() ? defaultWatermark : s.getWatermark())
                .expiresAt(s.getExpiresAt())
                .viewCount(s.getViewCount())
                .build();
    }

    private static Paragraph para(ParagraphResult p) {
        List<Sentence> sents = p.getSentences() == null ? List.of() : p.getSentences().stream()
                .map((SentenceResult x) -> new Sentence(x.getSentenceIdx(), x.getText(), x.getAiProb())).toList();
        return Paragraph.builder()
                .paragraphIdx(p.getParagraphIdx())
                .text(p.getText())
                .excluded(p.isExcluded())
                .excludeReason(p.getExcludeReason())
                .calibratedProb(p.getCalibratedProb())
                .sourceLabel(p.getSourceLabel())
                .sectionName(p.getSectionName())
                .sentences(sents)
                .build();
    }
}
