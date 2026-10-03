package com.paperaigc.detect.service;

import com.paperaigc.detect.domain.dto.AssistantChatDTO;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;

/**
 * 论文检测助手 —— Java 侧只做鉴权 / 限流 / 审计透传，LLM 与工具循环在 Python assistant/ 模块
 *
 * <p>设计见 docs/design/202610-paper-assistant-agent-research.md §3。</p>
 */
public interface IAssistantService {

    /**
     * 流式对话：把请求透传给 Python，把 SSE 事件逐帧转发给前端，结束时落审计
     * @param dto 对话请求（userId 由调用方按鉴权结果填好）
     * @return SseEmitter（已在后台线程开始写）
     */
    SseEmitter chat(AssistantChatDTO dto);

    /**
     * 会话列表
     * @param userId 用户 id
     * @param limit 条数
     * @return Python 原始列表（conversationId / title / taskId / updatedAt / turns）
     */
    List<Map<String, Object>> listConversations(Long userId, int limit);

    /**
     * 会话详情（消息列表）
     * @param conversationId 会话 id
     * @return Python 原始结构
     */
    Map<String, Object> getConversation(String conversationId);

    /**
     * 删除会话
     * @param conversationId 会话 id
     */
    void deleteConversation(String conversationId);

    /**
     * 快捷问题与欢迎语
     * @param taskId 可空；带任务时返回任务场景的问题
     * @return {welcome, prompts[]}
     */
    Map<String, Object> quickPrompts(Long taskId);

    /**
     * 助手健康（Python 侧 /assistant/health 透传 + Java 侧限流配置）
     * @return 健康信息
     */
    Map<String, Object> health();
}
