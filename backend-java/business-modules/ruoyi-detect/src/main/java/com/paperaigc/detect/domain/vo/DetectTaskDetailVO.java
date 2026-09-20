package com.paperaigc.detect.domain.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.paperaigc.detect.domain.entity.AudioSegmentResult;
import com.paperaigc.detect.domain.entity.DetectTask;
import com.paperaigc.detect.domain.entity.ImageSegmentResult;
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
    private String modality;   // text / audio / image
    private String paperTitle;
    private String status;
    private String scenario;
    private Integer threshold;
    private Double aiRate;
    private String modelVersion;
    private Integer wordCount;
    private Long bodyParagraphCount;
    private Integer excludedParagraphCount;
    private Double audioDurationSec;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime finishedAt;

    private List<ParagraphResult> paragraphs;             // text 模态
    private List<AudioSegmentResult> audioSegments;       // audio 模态
    private List<ImageSegmentResult> imageSegments;       // image 模态
    private Map<String, Double> sourceLabels;

    public static DetectTaskDetailVO from(DetectTask t) {
        if (t == null) return null;
        return DetectTaskDetailVO.builder()
                .id(t.getId())
                .userId(t.getUserId())
                .modality(t.getModality())
                .paperTitle(t.getPaperTitle())
                .status(t.getStatus())
                .scenario(t.getScenario())
                .threshold(t.getThreshold())
                .aiRate(t.getAiRate())
                .modelVersion(t.getModelVersion())
                .wordCount(t.getWordCount())
                .bodyParagraphCount(t.getBodyParagraphCount())
                .excludedParagraphCount(t.getExcludedParagraphCount())
                .audioDurationSec(t.getAudioDurationSec())
                .createdAt(t.getCreatedAt())
                .finishedAt(t.getFinishedAt())
                .paragraphs(t.getParagraphs())
                .audioSegments(t.getAudioSegments())
                .imageSegments(t.getImageSegments())
                .sourceLabels(t.getSourceLabels())
                .build();
    }
}
