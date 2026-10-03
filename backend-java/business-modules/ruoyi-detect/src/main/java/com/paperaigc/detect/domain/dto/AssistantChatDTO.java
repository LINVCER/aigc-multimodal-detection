package com.paperaigc.detect.domain.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

/**
 * 助手对话请求 —— 原样透传给 Python assistant/chat，Java 侧只补 userId 与审计
 */
@Data
public class AssistantChatDTO {

    @NotBlank(message = "message 不能为空")
    @Size(max = 4000, message = "message 不能超过 4000 字")
    private String message;

    /** 续接的会话；空则由 Python 新建并在首个 meta 事件里返回 */
    private String conversationId;

    /** 从报告详情页进入时带上的任务 id，作为对话默认上下文 */
    private Long taskId;

    /** 「为什么这段像 AI」直达的段落序号（0 起） */
    private Integer paragraphIdx;

    /** W3.c 前由前端透传；Sa-Token 真接入后以上下文为准、忽略此值 */
    private Long userId;

    private String locale = "zh-CN";

    /** 端 / 页面 / 版本，仅审计 */
    private Map<String, Object> clientContext;
}
