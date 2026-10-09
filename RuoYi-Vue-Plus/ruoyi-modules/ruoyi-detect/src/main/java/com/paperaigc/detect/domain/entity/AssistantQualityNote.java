package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 助手对话质检标注 —— assistant_quality_note（V0.3.0.007）
 *
 * <p>tag 固定五类：good / wrong_fact / off_point / boundary / tone，分别指向
 * 无需改 / 修工具或知识 / 补知识块 / 收紧边界规则 / 调提示词（增长闭环 §3）。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("assistant_quality_note")
public class AssistantQualityNote {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String conversationId;
    /** 具体哪一轮 assistant_log.id；空 = 整段会话 */
    private Long logId;
    /** 1-5 */
    private Integer score;
    private String tag;
    private String note;
    private Long reviewer;
    private LocalDateTime createdAt;
}
