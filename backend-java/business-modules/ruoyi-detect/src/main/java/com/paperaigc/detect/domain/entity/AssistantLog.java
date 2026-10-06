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
 * 助手对话审计 —— assistant_log
 *
 * <p>三个用途：误报分析、合规追溯（生成式 AI 服务要求日志留存）、
 * 统计「要求改写」类请求比例作为 humanize 是否重启的依据。Q/A 截断存，不存全文。</p>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("assistant_log")
public class AssistantLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long userId;
    private String conversationId;
    private Long taskId;

    /** 用户问题（截断 500 字） */
    private String question;
    /** 助手回答（截断 1000 字） */
    private String answer;

    /** 意图标签：explain / policy / guide / appeal / rewrite_request / history / chitchat / other */
    private String intent;
    /** 本轮调用的工具名，逗号分隔 */
    private String tools;

    private String model;
    private Integer promptTokens;
    private Integer completionTokens;
    private Integer latencyMs;

    /** stop / tool_calls / safety / error / tool_rounds_exceeded */
    private String finishReason;
    /** 内容安全结果：pass / blocked / degraded */
    private String safety;
    /** 回答疑似越界（针对原文给出成品改写）：人工抽查用 */
    private Boolean boundaryFlag;
    /** 越界类型：rewrite / bypass / ghostwrite / appeal_fabricate（boundaryFlag=true 时非空） */
    private String boundaryType;
    /** 错误码（有则本轮失败） */
    private String errorCode;

    /** 端 / 页面 / 版本（JSON 文本） */
    private String clientContext;

    private LocalDateTime createdAt;
}
