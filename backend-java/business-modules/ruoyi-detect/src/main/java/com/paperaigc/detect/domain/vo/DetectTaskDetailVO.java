package com.paperaigc.detect.domain.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ParagraphResult;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 任务详情视图 —— 含 paragraphs 与 sourceLabels，供报告页展开
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DetectTaskDetailVO {

    private Long id;
    private Long userId;
    private String paperTitle;
    private String status;
    private String scenario;
    private Integer threshold;
    private Double aiRate;
    private String modelVersion;
    private Integer wordCount;
    private Long bodyParagraphCount;
    private Integer excludedParagraphCount;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime finishedAt;

    private List<ParagraphResult> paragraphs;
    private Map<String, Double> sourceLabels;

    public static DetectTaskDetailVO from(DetectTask t) {
        if (t == null) return null;
        return DetectTaskDetailVO.builder()
                .id(t.getId())
                .userId(t.getUserId())
                .paperTitle(t.getPaperTitle())
                .status(t.getStatus())
                .scenario(t.getScenario())
                .threshold(t.getThreshold())
                .aiRate(t.getAiRate())
                .modelVersion(t.getModelVersion())
                .wordCount(t.getWordCount())
                .bodyParagraphCount(t.getBodyParagraphCount())
                .excludedParagraphCount(t.getExcludedParagraphCount())
                .createdAt(t.getCreatedAt())
                .finishedAt(t.getFinishedAt())
                .paragraphs(t.getParagraphs())
                .sourceLabels(t.getSourceLabels())
                .build();
    }
}
