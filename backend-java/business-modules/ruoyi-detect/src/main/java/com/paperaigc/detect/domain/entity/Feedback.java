package com.paperaigc.detect.domain.entity;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 用户反馈实体 —— 对齐 scripts/patch-schema.sql · user_feedback
 *
 * <p>Phase 0 内存态，Phase B 接入 MyBatis-Plus 时补 @TableName / @TableId / @TableField 注解。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Feedback {

    /** 反馈 ID */
    private Long id;
    /** 提交用户 ID（Sa-Token 接入后从上下文取；未登录场景为 null） */
    private Long userId;
    /** 分类：bug / suggestion / appeal */
    private String category;
    /** 结果申诉时关联的检测任务 ID */
    private Long taskId;
    /** 反馈内容 ≤ 2000 字 */
    private String content;
    /** 联系方式（选填） */
    private String contact;
    /** 状态：PENDING / PROCESSING / REPLIED / IGNORED */
    private String status;
    /** 处理的运营账号 ID */
    private Long handledBy;
    /** 处理回复文本 */
    private String handledReply;
    /** 处理时间 */
    private LocalDateTime handledAt;
    /** 提交时间 */
    private LocalDateTime createdAt;
}
