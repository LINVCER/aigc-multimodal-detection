package com.paperaigc.detect.domain.entity;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import com.baomidou.mybatisplus.extension.handlers.JacksonTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 助手会话 —— assistant_conversation（V0.3.0.004，Python session._MysqlStore 写入）
 *
 * <p>Java 侧只读，供运营质检看完整对话。messages 结构：[{role, content, ts, tools?, blocked?}]。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "assistant_conversation", autoResultMap = true)
public class AssistantConversation {

    @TableId(type = IdType.AUTO)
    private Long id;

    private String conversationId;
    private Long userId;
    private Long taskId;
    private String title;

    @TableField(value = "messages_json", typeHandler = JacksonTypeHandler.class)
    private List<Map<String, Object>> messages;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
