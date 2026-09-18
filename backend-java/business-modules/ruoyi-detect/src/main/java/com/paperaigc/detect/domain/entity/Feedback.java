package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 用户反馈实体 —— 对齐 docs/releases/v0.1.0/sql · user_feedback
 *
 * <p>Phase B 接入 MyBatis-Plus，字段与表列映射由 map-underscore-to-camel-case 处理。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("user_feedback")
public class Feedback {

    /** 反馈 ID */
    @TableId(type = IdType.AUTO)
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
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;
}
