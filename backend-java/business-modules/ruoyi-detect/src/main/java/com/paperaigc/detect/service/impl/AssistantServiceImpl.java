package com.paperaigc.detect.service.impl;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.paperaigc.detect.common.enums.ErrorCode;
import com.paperaigc.detect.common.exception.BizException;
import com.paperaigc.detect.domain.dto.AssistantChatDTO;
import com.paperaigc.detect.domain.entity.AssistantLog;
import com.paperaigc.detect.mapper.AssistantLogMapper;
import com.paperaigc.detect.service.IAssistantService;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 助手透传实现
 *
 * <p>SSE 转发用 JDK HttpClient 的 ofInputStream 逐行读 Python 的事件流，按空行切帧后用
 * SseEmitter 原样下发；同时截获 meta / done / error 三类事件填审计。
 * 限流用 Caffeine 两个计数器（每用户每分钟 / 每日），与 ScenarioThreshold 的缓存同一套依赖。</p>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AssistantServiceImpl implements IAssistantService {

    private final AssistantLogMapper logMapper;

    @Value("${platform.assistant.base-url:http://localhost:8000}")
    private String pyBaseUrl;

    @Value("${platform.assistant.rate-per-minute:8}")
    private int ratePerMinute;

    @Value("${platform.assistant.rate-per-day:100}")
    private int ratePerDay;

    @Value("${platform.assistant.stream-timeout-seconds:120}")
    private int streamTimeoutSeconds;

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final HttpClient httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_1_1)
            .connectTimeout(Duration.ofSeconds(5))
            .build();
    /** SSE 转发线程池：每个在线对话占一个线程，内测规模够用；上量后换虚拟线程或 WebFlux */
    private final ExecutorService streamPool = Executors.newCachedThreadPool(r -> {
        Thread t = new Thread(r, "assistant-sse");
        t.setDaemon(true);
        return t;
    });

    private final Cache<String, AtomicInteger> perMinute = Caffeine.newBuilder()
            .expireAfterWrite(Duration.ofMinutes(1)).maximumSize(100_000).build();
    private final Cache<String, AtomicInteger> perDay = Caffeine.newBuilder()
            .expireAfterWrite(Duration.ofDays(1)).maximumSize(100_000).build();

    @PreDestroy
    void shutdown() {
        streamPool.shutdownNow();
    }

    /* ==================== 对话 ==================== */

    @Override
    public SseEmitter chat(AssistantChatDTO dto) {
        String rateKey = dto.getUserId() == null ? "anon" : String.valueOf(dto.getUserId());
        checkRate(rateKey);

        SseEmitter emitter = new SseEmitter(streamTimeoutSeconds * 1000L);
        AssistantLog.AssistantLogBuilder audit = AssistantLog.builder()
                .userId(dto.getUserId()).taskId(dto.getTaskId()).conversationId(dto.getConversationId())
                .question(truncate(dto.getMessage(), 500))
                .clientContext(toJsonSafe(dto.getClientContext()))
                .createdAt(LocalDateTime.now());

        streamPool.submit(() -> forward(dto, emitter, audit));
        return emitter;
    }

    private void checkRate(String key) {
        int m = perMinute.get(key, k -> new AtomicInteger()).incrementAndGet();
        if (m > ratePerMinute) {
            throw new BizException(ErrorCode.ASSISTANT_RATE_LIMITED, "问得太快了，请 1 分钟后再试");
        }
        int d = perDay.get(key, k -> new AtomicInteger()).incrementAndGet();
        if (d > ratePerDay) {
            throw new BizException(ErrorCode.ASSISTANT_RATE_LIMITED, "今天的提问次数已用完，明天再来");
        }
    }

    private void forward(AssistantChatDTO dto, SseEmitter emitter, AssistantLog.AssistantLogBuilder audit) {
        long t0 = System.currentTimeMillis();
        StringBuilder answer = new StringBuilder();
        try {
            String body = objectMapper.writeValueAsString(dto);
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(pyBaseUrl + "/api/v1/assistant/chat"))
                    .header("Content-Type", "application/json")
                    .header("Accept", "text/event-stream")
                    .timeout(Duration.ofSeconds(streamTimeoutSeconds))
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
            HttpResponse<InputStream> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofInputStream());
            if (resp.statusCode() >= 400) {
                sendError(emitter, "ASSISTANT_UPSTREAM_ERROR", "助手服务返回 " + resp.statusCode(), true);
                audit.errorCode("UPSTREAM_" + resp.statusCode());
                return;
            }

            try (BufferedReader br = new BufferedReader(new InputStreamReader(resp.body(), StandardCharsets.UTF_8))) {
                String event = null;
                StringBuilder data = new StringBuilder();
                String line;
                while ((line = br.readLine()) != null) {
                    if (line.isEmpty()) {
                        if (event != null) {
                            handleFrame(event, data.toString(), emitter, audit, answer);
                        }
                        event = null;
                        data.setLength(0);
                        continue;
                    }
                    if (line.startsWith("event:")) {
                        event = line.substring(6).trim();
                    } else if (line.startsWith("data:")) {
                        if (data.length() > 0) data.append('\n');
                        data.append(line.substring(5).trim());
                    }
                }
                if (event != null) {
                    handleFrame(event, data.toString(), emitter, audit, answer);
                }
            }
            emitter.complete();
        } catch (Exception e) {
            log.warn("assistant 透传失败: {}", e.toString());
            audit.errorCode(e.getClass().getSimpleName());
            sendError(emitter, "ASSISTANT_UPSTREAM_ERROR", "助手服务暂时不可用，请稍后再试", true);
        } finally {
            audit.latencyMs((int) (System.currentTimeMillis() - t0));
            audit.answer(truncate(answer.toString(), 1000));
            saveAudit(audit.build());
        }
    }

    @SuppressWarnings("unchecked")
    private void handleFrame(String event, String data, SseEmitter emitter,
                             AssistantLog.AssistantLogBuilder audit, StringBuilder answer) throws Exception {
        // 原样下发给前端
        emitter.send(SseEmitter.event().name(event).data(data));

        // 顺手截审计字段
        switch (event) {
            case "meta" -> {
                Map<String, Object> m = objectMapper.readValue(data, Map.class);
                audit.conversationId(str(m.get("conversationId"))).model(str(m.get("model"))).intent(str(m.get("intent")));
            }
            case "token" -> {
                Map<String, Object> m = objectMapper.readValue(data, Map.class);
                Object delta = m.get("delta");
                if (delta != null && answer.length() < 4000) answer.append(delta);
            }
            case "done" -> {
                Map<String, Object> m = objectMapper.readValue(data, Map.class);
                Map<String, Object> usage = (Map<String, Object>) m.getOrDefault("usage", Map.of());
                audit.promptTokens(toInt(usage.get("prompt_tokens")))
                        .completionTokens(toInt(usage.get("completion_tokens")))
                        .finishReason(str(m.get("finishReason")))
                        .safety(str(m.get("safety")))
                        .boundaryFlag(Boolean.TRUE.equals(m.get("boundaryFlag")))
                        .boundaryType(str(m.get("boundaryType")));
                if (m.get("intent") != null) audit.intent(str(m.get("intent")));
                Object tools = m.get("tools");
                if (tools instanceof List<?> l && !l.isEmpty()) audit.tools(String.join(",", l.stream().map(String::valueOf).toList()));
            }
            case "error" -> {
                Map<String, Object> m = objectMapper.readValue(data, Map.class);
                audit.errorCode(str(m.get("code"))).finishReason("error");
            }
            default -> { /* tool_call / tool_result 不入审计主字段，done.tools 已汇总 */ }
        }
    }

    private void sendError(SseEmitter emitter, String code, String message, boolean retryable) {
        try {
            Map<String, Object> payload = Map.of("code", code, "message", message, "retryable", retryable);
            emitter.send(SseEmitter.event().name("error").data(objectMapper.writeValueAsString(payload)));
            emitter.complete();
        } catch (Exception ignore) {
            emitter.completeWithError(new RuntimeException(message));
        }
    }

    private void saveAudit(AssistantLog row) {
        try {
            logMapper.insert(row);
        } catch (Exception e) {
            // 审计表缺失（迁移未跑）不阻断对话
            log.warn("assistant_log 写入失败: {}", e.getMessage());
        }
    }

    /* ==================== 非流式透传 ==================== */

    @Override
    public List<Map<String, Object>> listConversations(Long userId, int limit) {
        String q = "?limit=" + limit + (userId == null ? "" : "&userId=" + userId);
        return getJson("/api/v1/assistant/conversations" + q, new TypeReference<List<Map<String, Object>>>() {});
    }

    @Override
    public Map<String, Object> getConversation(String conversationId) {
        return getJson("/api/v1/assistant/conversations/" + conversationId, new TypeReference<Map<String, Object>>() {});
    }

    @Override
    public void deleteConversation(String conversationId) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(pyBaseUrl + "/api/v1/assistant/conversations/" + conversationId))
                    .timeout(Duration.ofSeconds(8)).DELETE().build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() >= 400) throw new BizException(ErrorCode.ASSISTANT_UPSTREAM_ERROR);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            throw new BizException(ErrorCode.ASSISTANT_UPSTREAM_ERROR);
        }
    }

    @Override
    public Map<String, Object> quickPrompts(Long taskId) {
        return getJson("/api/v1/assistant/quick-prompts" + (taskId == null ? "" : "?taskId=" + taskId), new TypeReference<Map<String, Object>>() {});
    }

    @Override
    public Map<String, Object> health() {
        Map<String, Object> out = new HashMap<>();
        out.put("ratePerMinute", ratePerMinute);
        out.put("ratePerDay", ratePerDay);
        out.put("pythonBaseUrl", pyBaseUrl);
        try {
            out.put("python", getJson("/api/v1/assistant/health", new TypeReference<Map<String, Object>>() {}));
            out.put("reachable", true);
        } catch (Exception e) {
            out.put("reachable", false);
            out.put("error", e.getMessage());
        }
        return out;
    }

    private <T> T getJson(String path, TypeReference<T> type) {
        try {
            HttpRequest req = HttpRequest.newBuilder()
                    .uri(URI.create(pyBaseUrl + path))
                    .timeout(Duration.ofSeconds(8)).GET().build();
            HttpResponse<String> resp = httpClient.send(req, HttpResponse.BodyHandlers.ofString());
            if (resp.statusCode() == 404) throw new BizException(ErrorCode.NOT_FOUND);
            if (resp.statusCode() >= 400) throw new BizException(ErrorCode.ASSISTANT_UPSTREAM_ERROR);
            return objectMapper.readValue(resp.body(), type);
        } catch (BizException e) {
            throw e;
        } catch (Exception e) {
            log.warn("assistant GET {} 失败: {}", path, e.toString());
            throw new BizException(ErrorCode.ASSISTANT_UPSTREAM_ERROR);
        }
    }

    /* ==================== helpers ==================== */

    private static String truncate(String s, int n) {
        if (s == null) return null;
        return s.length() <= n ? s : s.substring(0, n);
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private static Integer toInt(Object o) {
        return o instanceof Number n ? n.intValue() : null;
    }

    private String toJsonSafe(Object o) {
        if (o == null) return null;
        try {
            return truncate(objectMapper.writeValueAsString(o), 500);
        } catch (Exception e) {
            return null;
        }
    }
}
