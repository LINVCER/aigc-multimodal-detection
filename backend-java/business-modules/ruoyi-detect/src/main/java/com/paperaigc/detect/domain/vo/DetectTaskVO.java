package com.paperaigc.detect.domain.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.paperaigc.detect.domain.entity.DetectTask;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 任务列表视图（不含 paragraphs / sourceLabels，避免大字段传输）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DetectTaskVO {

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

    public static DetectTaskVO from(DetectTask t) {
        if (t == null) return null;
        return DetectTaskVO.builder()
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
                .build();
    }
}
