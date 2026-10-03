package com.paperaigc.detect.controller;

import cn.dev33.satoken.annotation.SaIgnore;
import com.paperaigc.detect.domain.dto.AssistantChatDTO;
import com.paperaigc.detect.service.IAssistantService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.dromara.common.core.domain.R;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;
import java.util.Map;

/**
 * 论文检测助手接口 —— /api/v1/assistant/*
 *
 * <p>Java 只做鉴权 / 限流 / 审计透传；LLM、工具循环、知识库、会话存储都在 Python assistant/ 模块。
 * 设计见 docs/design/202610-paper-assistant-agent-research.md。</p>
 *
 * <p>@SaIgnore 与其它 Controller 口径一致（W3.c Sa-Token 真接入时统一收敛）；userId 当前由前端透传或 X-User-Id 头。</p>
 */
@Slf4j
@SaIgnore
@RestController
@RequestMapping("/api/v1/assistant")
@RequiredArgsConstructor
public class AssistantController {

    private final IAssistantService assistantService;

    /**
     * 流式对话（SSE）。事件：meta / token / tool_call / tool_result / done / error
     */
    @PostMapping(value = "/chat", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter chat(@Valid @RequestBody AssistantChatDTO dto,
                           @RequestHeader(value = "X-User-Id", required = false) Long headerUserId) {
        if (dto.getUserId() == null && headerUserId != null) dto.setUserId(headerUserId);
        return assistantService.chat(dto);
    }

    @GetMapping("/conversations")
    public R<List<Map<String, Object>>> conversations(@RequestParam(value = "userId", required = false) Long userId,
                                                      @RequestParam(value = "limit", defaultValue = "20") int limit,
                                                      @RequestHeader(value = "X-User-Id", required = false) Long headerUserId) {
        return R.ok(assistantService.listConversations(userId != null ? userId : headerUserId, Math.min(Math.max(limit, 1), 50)));
    }

    @GetMapping("/conversations/{id}")
    public R<Map<String, Object>> conversation(@PathVariable("id") String id) {
        return R.ok(assistantService.getConversation(id));
    }

    @DeleteMapping("/conversations/{id}")
    public R<Void> deleteConversation(@PathVariable("id") String id) {
        assistantService.deleteConversation(id);
        return R.ok();
    }

    @GetMapping("/quick-prompts")
    public R<Map<String, Object>> quickPrompts(@RequestParam(value = "taskId", required = false) Long taskId) {
        return R.ok(assistantService.quickPrompts(taskId));
    }

    @GetMapping("/health")
    public R<Map<String, Object>> health() {
        return R.ok(assistantService.health());
    }
}
