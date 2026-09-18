package com.paperaigc.detect.domain.vo;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.paperaigc.detect.domain.entity.Feedback;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 反馈响应
 *
 * <p>与 Entity 字段一致，仅 LocalDateTime 序列化为 "yyyy-MM-dd HH:mm:ss"。
 * 未来若要脱敏 contact / 隐藏 handledBy 时在此收敛。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FeedbackVO {

    private Long id;
    private Long userId;
    private String category;
    private Long taskId;
    private String content;
    private String contact;
    private String status;
    private Long handledBy;
    private String handledReply;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime handledAt;

    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private LocalDateTime createdAt;

    /** Entity → VO */
    public static FeedbackVO from(Feedback f) {
        if (f == null) return null;
        return FeedbackVO.builder()
                .id(f.getId())
                .userId(f.getUserId())
                .category(f.getCategory())
                .taskId(f.getTaskId())
                .content(f.getContent())
                .contact(f.getContact())
                .status(f.getStatus())
                .handledBy(f.getHandledBy())
                .handledReply(f.getHandledReply())
                .handledAt(f.getHandledAt())
                .createdAt(f.getCreatedAt())
                .build();
    }
}
